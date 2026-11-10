"""Drift-triggered retraining: watch each deployment's live inputs and queue a retrain on a breach.

Every RETRAIN_CHECK_INTERVAL_S the controller, for each active deployment whose policy has
`retrain.enabled`:
  1. runs `compute_drift` (app/services/drift.py) on the last `window` prediction logs of the
     deployment's current model against that model's training baseline from the registry;
  2. asks `should_retrain` (shared/lifecycle/policy.py) whether the breach, cooldown, in-flight
     retrains and the number of labelled samples justify a retrain;
  3. if so, records `drift_detected` + `retrain_queued` events and calls training-service /retrain,
     which evaluates the candidate behind the promotion gate.
"""

import ast
import json
import os
import threading
import time
from datetime import timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from shared.database import SessionLocal
from shared.lifecycle.events import load_policy, record_event
from shared.lifecycle.policy import RetrainPolicy, should_retrain
from shared.models.deployment import Deployment
from shared.models.lifecycle import LabelledSample, LifecycleEvent
from shared.models.model_registry import ModelRegistry
from shared.models.monitoring import PredictionLog
from shared.models.training_job import TrainingJob

from app.services.drift import compute_drift

TRAINING_SERVICE_URL = os.environ.get("TRAINING_SERVICE_URL", "http://training-service:8000")
CHECK_INTERVAL_S = float(os.environ.get("RETRAIN_CHECK_INTERVAL_S", "60"))


# ── Helpers shared with the /drift route ─────────────────────────────────────

def registry_metadata(db, model_id: int) -> Optional[Dict[str, Any]]:
    m = db.query(ModelRegistry.metadata_json).filter(ModelRegistry.id == model_id).first()
    if not m or not m[0]:
        return None
    try:
        return json.loads(m[0])
    except ValueError:
        return None


def recent_logs(db, model_id: int, window: int) -> List[PredictionLog]:
    return (db.query(PredictionLog)
            .filter(PredictionLog.model_id == model_id)
            .order_by(PredictionLog.id.desc())
            .limit(window).all())


def inputs_from_logs(logs) -> Tuple[Dict[str, list], int]:
    """{feature: [values]} from the logged input_data (JSON or a Python dict repr)."""
    current: Dict[str, list] = {}
    errors = 0
    for log in logs:
        try:
            raw = log.input_data
            data = json.loads(raw) if raw.startswith("{\"") else ast.literal_eval(raw)
            for feature, value in data.items():
                try:
                    current.setdefault(feature, []).append(float(value))
                except (TypeError, ValueError):
                    current.setdefault(feature, []).append(value)
        except Exception:
            errors += 1
    return current, errors


def drift_for_model(db, model_id: int, window: int, min_samples: int) -> Optional[Dict[str, Any]]:
    meta = registry_metadata(db, model_id)
    baseline = (meta or {}).get("training_distribution")
    if not baseline:
        return None
    logs = recent_logs(db, model_id, window)
    current, _ = inputs_from_logs(logs)
    result = compute_drift(baseline=baseline, current_data=current, min_samples=min_samples)
    result["logs_analysed"] = len(logs)
    return result


def _last_retrain(db, deployment_id: int) -> Tuple[Optional[float], bool]:
    """(unix time of the last queued retrain, whether that retrain is still queued/running)."""
    ev = (db.query(LifecycleEvent)
          .filter(LifecycleEvent.deployment_id == deployment_id, LifecycleEvent.event_type == "retrain_queued")
          .order_by(LifecycleEvent.id.desc()).first())
    if not ev:
        return None, False
    in_flight = False
    job_id = (json.loads(ev.details_json or "{}")).get("job_id")
    if job_id:
        job = db.query(TrainingJob.status).filter(TrainingJob.id == job_id).first()
        in_flight = bool(job and job[0] in ("queued", "running"))
    # created_at is naive UTC
    return ev.created_at.replace(tzinfo=timezone.utc).timestamp(), in_flight


def _summary(drift: Dict[str, Any]) -> Dict[str, Any]:
    feats = drift.get("features") or {}
    return {
        "overall_psi": drift.get("overall_psi"),
        "overall_drift": drift.get("overall_drift"),
        "drifted_features": drift.get("drifted_features"),
        "logs_analysed": drift.get("logs_analysed"),
        "per_feature": {k: {"psi": v.get("psi"), "ks": v.get("ks_statistic")} for k, v in feats.items()
                        if v.get("psi") is not None},
    }


# ── One check, used by the loop and by POST /deployments/{id}/lifecycle-check ─

def check_deployment(db, dep: Deployment, now: Optional[float] = None, queue: bool = True) -> Dict[str, Any]:
    now = time.time() if now is None else now
    policy = RetrainPolicy.from_dict(load_policy(db, dep.id)["retrain"])
    drift = drift_for_model(db, dep.model_id, policy.window, policy.min_samples)
    if drift is None:
        return {"deployment_id": dep.id, "retrain": False, "reason": "model has no training baseline"}
    last_at, in_flight = _last_retrain(db, dep.id)
    labelled = db.query(LabelledSample).filter(LabelledSample.deployment_id == dep.id).count()
    decision = should_retrain(drift, policy, labelled_count=labelled, retrain_in_flight=in_flight,
                              last_retrain_at=last_at, now=now)
    out = {"deployment_id": dep.id, "model_id": dep.model_id, "retrain": decision.retrain,
           "reason": decision.reason, "breaches": decision.breaches, "labelled": labelled,
           "drift": _summary(drift)}
    if not (decision.retrain and queue):
        return out

    record_event(db, "drift_detected", deployment_id=dep.id, from_model_id=dep.model_id,
                 reason="; ".join(decision.breaches[:5]), details=out["drift"])
    r = requests.post(f"{TRAINING_SERVICE_URL}/retrain", timeout=30, json={
        "deployment_id": dep.id, "live_model_id": dep.model_id,
        "trigger": {"breaches": decision.breaches, "overall_psi": drift.get("overall_psi")}})
    r.raise_for_status()
    job_id = r.json()["job_id"]
    record_event(db, "retrain_queued", deployment_id=dep.id, from_model_id=dep.model_id,
                 reason=f"retrain job {job_id} on {min(labelled, policy.labelled_window)} labelled samples",
                 details={"job_id": job_id, "labelled": labelled})
    out["job_id"] = job_id
    return out


class RetrainController:
    def __init__(self, interval_s: float = CHECK_INTERVAL_S):
        self.interval_s = interval_s
        self._stop = threading.Event()
        self.last_run: Optional[float] = None
        self.last_results: List[Dict[str, Any]] = []
        self.last_error: Optional[str] = None

    def start(self):
        threading.Thread(target=self._loop, name="retrain-controller", daemon=True).start()

    def _loop(self):
        while not self._stop.wait(self.interval_s):
            db = SessionLocal()
            try:
                results = []
                for dep in db.query(Deployment).filter(Deployment.status == "active").all():
                    if not load_policy(db, dep.id)["retrain"]["enabled"]:
                        continue
                    results.append(check_deployment(db, dep))
                self.last_results, self.last_run, self.last_error = results, time.time(), None
            except Exception as e:
                db.rollback()
                self.last_error = repr(e)
                print("Retrain controller error:", repr(e))
            finally:
                db.close()


controller = RetrainController()
