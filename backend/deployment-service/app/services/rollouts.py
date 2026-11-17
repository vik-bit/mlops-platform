"""Serving through a deployment, with shadow/canary rollouts and the controller that judges them.

Request path (`serve`):
  1. Look up the deployment's stable model and active rollout (cached per pod for ROUTING_TTL_S).
  2. `choose_arm` picks the answering model: shadow -> stable; canary -> candidate for N% of requests.
  3. Shadow mode also scores the candidate on a background thread; its result is logged, never returned.
  4. Every scored prediction is logged (async) to the monitoring service under its model id.

Controller (`RolloutController`, one thread per pod):
  Every ROLLOUT_EVAL_INTERVAL_S it reads both arms' prediction logs since the rollout started,
  runs `evaluate_rollout`, and acts. Actions are conditional UPDATEs on status='active', so when
  several replicas evaluate the same rollout only one of them records the rollback/promotion.
"""

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import pandas as pd
from sqlalchemy import update

from shared.database import SessionLocal
from shared.lifecycle.events import load_policy, record_event
from shared.lifecycle.policy import ArmStats, RolloutThresholds, choose_arm, evaluate_rollout
from shared.models.deployment import Deployment
from shared.models.lifecycle import Rollout
from shared.models.model_registry import ModelRegistry
from shared.models.monitoring import PredictionLog

from app.services import metrics
from app.services.logger import log_prediction
from app.services.model_loader import load_model

ROUTING_TTL_S = float(os.environ.get("ROUTING_TTL_S", "1.0"))
EVAL_INTERVAL_S = float(os.environ.get("ROLLOUT_EVAL_INTERVAL_S", "5"))
EVAL_MAX_LOGS = int(os.environ.get("ROLLOUT_EVAL_MAX_LOGS", "5000"))
SHADOW_WORKERS = int(os.environ.get("SHADOW_WORKERS", "2"))
SHADOW_MAX_INFLIGHT = int(os.environ.get("SHADOW_MAX_INFLIGHT", "64"))


class NotFound(Exception):
    pass


# ── Routing table (per pod, short TTL) ───────────────────────────────────────

class _Route:
    __slots__ = ("stable_model_id", "rollout_id", "candidate_model_id", "mode", "traffic_percent", "expires")

    def __init__(self, stable_model_id, rollout: Optional[Rollout], ttl: float):
        self.stable_model_id = stable_model_id
        self.rollout_id = rollout.id if rollout else None
        self.candidate_model_id = rollout.candidate_model_id if rollout else None
        self.mode = rollout.mode if rollout else None
        self.traffic_percent = rollout.traffic_percent if rollout else 0.0
        self.expires = time.monotonic() + ttl


_routes: Dict[int, _Route] = {}
_routes_lock = threading.Lock()


def get_route(deployment_id: int) -> _Route:
    now = time.monotonic()
    route = _routes.get(deployment_id)
    if route and route.expires > now:
        return route
    db = SessionLocal()
    try:
        dep = db.query(Deployment).filter(Deployment.id == deployment_id).first()
        if not dep or dep.status != "active":
            raise NotFound(f"Deployment {deployment_id} not found or not active")
        rollout = (db.query(Rollout)
                   .filter(Rollout.deployment_id == deployment_id, Rollout.status == "active")
                   .order_by(Rollout.id.desc()).first())
        route = _Route(dep.model_id, rollout, ROUTING_TTL_S)
    finally:
        db.close()
    with _routes_lock:
        _routes[deployment_id] = route
    return route


def invalidate_route(deployment_id: int):
    with _routes_lock:
        _routes.pop(deployment_id, None)


# ── Scoring ──────────────────────────────────────────────────────────────────

def _native(val):
    return val.item() if hasattr(val, "item") else val


def _score(model_id: int, features: Dict[str, Any], return_proba: bool) -> Tuple[Any, Optional[dict], float]:
    """Predict one row; returns (prediction, probabilities, inference latency in ms).

    The (cached) model load happens before the clock starts: a pod's first request for a model
    would otherwise report the unpickle time as latency and could trip the p95 rule.
    """
    pipeline = load_model(model_id)
    t0 = time.perf_counter()
    df = pd.DataFrame([features])
    pred = _native(pipeline.predict(df)[0])
    proba = None
    if return_proba:
        step = getattr(pipeline, "named_steps", {}).get("model")
        if step is not None and hasattr(step, "predict_proba"):
            p = pipeline.predict_proba(df)[0]
            proba = {str(c): round(float(v), 4) for c, v in zip(step.classes_, p)}
    return pred, proba, round((time.perf_counter() - t0) * 1000, 3)


_shadow_pool = ThreadPoolExecutor(max_workers=SHADOW_WORKERS, thread_name_prefix="shadow")
_shadow_slots = threading.BoundedSemaphore(SHADOW_MAX_INFLIGHT)


def _shadow_score(model_id: int, features: Dict[str, Any]):
    try:
        t0 = time.perf_counter()
        try:
            pred, _, latency = _score(model_id, features, False)
            log_prediction(model_id, features, pred, latency, "success")
            metrics.observe(model_id, "shadow", "success", latency)
        except Exception as e:
            latency = round((time.perf_counter() - t0) * 1000, 3)
            log_prediction(model_id, features, f"error: {e}", latency, "failed")
            metrics.observe(model_id, "shadow", "failed", latency)
    finally:
        _shadow_slots.release()


def serve(deployment_id: int, features: Dict[str, Any], return_proba: bool = False) -> Dict[str, Any]:
    """Answer one prediction through the deployment. Raises NotFound, or the model's own exception."""
    route = get_route(deployment_id)
    arm = choose_arm(route.mode or "", route.traffic_percent) if route.rollout_id else "stable"
    model_id = route.candidate_model_id if arm == "candidate" else route.stable_model_id

    t0 = time.perf_counter()
    try:
        pred, proba, latency = _score(model_id, features, return_proba)
    except Exception as e:
        latency = round((time.perf_counter() - t0) * 1000, 3)
        log_prediction(model_id, features, f"error: {e}", latency, "failed")
        metrics.observe(model_id, arm, "failed", latency)
        raise
    log_prediction(model_id, features, pred, latency, "success")
    metrics.observe(model_id, arm, "success", latency)

    if route.rollout_id and route.mode == "shadow":
        if _shadow_slots.acquire(blocking=False):
            _shadow_pool.submit(_shadow_score, route.candidate_model_id, features)
        else:
            metrics.SHADOW_SKIPPED.inc()

    return {
        "prediction": pred,
        "probability": proba,
        "latency_ms": latency,
        "model_id": model_id,
        "arm": arm,
        "rollout_id": route.rollout_id,
    }


# ── Promotion / rollback (idempotent across replicas) ───────────────────────

def _set_stage(db, model_id: int, stage: str):
    m = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
    if m:
        m.stage = stage


def finish_rollout(db, rollout: Rollout, outcome: str, reason: str, details: Optional[dict] = None,
                   actor: str = "controller") -> bool:
    """Move an active rollout to `outcome` ("promoted" | "rolled_back" | "cancelled").

    Returns False if another replica (or a person) already finished it.
    """
    res = db.execute(
        update(Rollout)
        .where(Rollout.id == rollout.id, Rollout.status == "active")
        .values(status=outcome, ended_at=datetime.utcnow(), decision_reason=reason,
                last_metrics_json=json.dumps(details.get("metrics")) if details and "metrics" in details
                else Rollout.last_metrics_json)
    )
    if res.rowcount != 1:
        db.rollback()
        return False

    event_type = {"promoted": "promoted", "rolled_back": "rolled_back", "cancelled": "rollout_cancelled"}[outcome]
    if outcome == "promoted":
        dep = db.query(Deployment).filter(Deployment.id == rollout.deployment_id).first()
        dep.model_id = rollout.candidate_model_id
        dep.endpoint = f"/deployments/{dep.id}/predict"
        _set_stage(db, rollout.candidate_model_id, "production")
        _set_stage(db, rollout.stable_model_id, "archived")
    elif outcome == "rolled_back":
        _set_stage(db, rollout.candidate_model_id, "rejected")
    else:
        _set_stage(db, rollout.candidate_model_id, "staging")

    record_event(db, event_type, deployment_id=rollout.deployment_id, rollout_id=rollout.id,
                 from_model_id=rollout.stable_model_id, to_model_id=rollout.candidate_model_id,
                 reason=reason, details={**(details or {}), "actor": actor,
                                         "mode": rollout.mode, "traffic_percent": rollout.traffic_percent,
                                         "started_at": rollout.started_at.isoformat() + "Z"},
                 commit=False)
    db.commit()
    invalidate_route(rollout.deployment_id)
    return True


def start_rollout(db, deployment_id: int, candidate_model_id: int, mode: str, traffic_percent: float,
                  thresholds: Optional[dict], actor: str, reason: Optional[str] = None) -> Rollout:
    if mode not in ("shadow", "canary"):
        raise ValueError("mode must be 'shadow' or 'canary'")
    if mode == "canary" and not 0 < traffic_percent <= 100:
        raise ValueError("canary traffic_percent must be in (0, 100]")
    dep = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not dep or dep.status != "active":
        raise NotFound(f"Deployment {deployment_id} not found or not active")
    if candidate_model_id == dep.model_id:
        raise ValueError("candidate is already the stable model")
    if not db.query(ModelRegistry).filter(ModelRegistry.id == candidate_model_id).first():
        raise NotFound(f"Model {candidate_model_id} not found")
    if db.query(Rollout).filter(Rollout.deployment_id == deployment_id, Rollout.status == "active").first():
        raise RuntimeError("this deployment already has an active rollout")

    load_model(candidate_model_id)  # fail now, not on the first routed request, if it cannot be loaded

    merged = load_policy(db, deployment_id)["rollout"]
    merged.update(thresholds or {})
    t = RolloutThresholds.from_dict(merged)
    rollout = Rollout(deployment_id=deployment_id, stable_model_id=dep.model_id,
                      candidate_model_id=candidate_model_id, mode=mode,
                      traffic_percent=traffic_percent if mode == "canary" else 0.0,
                      status="active", thresholds_json=json.dumps(t.to_dict()))
    db.add(rollout)
    db.flush()
    _set_stage(db, candidate_model_id, mode)
    record_event(db, f"{mode}_started", deployment_id=deployment_id, rollout_id=rollout.id,
                 from_model_id=dep.model_id, to_model_id=candidate_model_id,
                 reason=reason or f"{mode} started by {actor}",
                 details={"traffic_percent": rollout.traffic_percent, "thresholds": t.to_dict(), "actor": actor},
                 commit=False)
    db.commit()
    db.refresh(rollout)
    invalidate_route(deployment_id)
    return rollout


def promote_directly(db, deployment_id: int, model_id: int, reason: str, details: Optional[dict], actor: str):
    """Swap the stable model without a rollout (used by the retrain gate's "direct" mode)."""
    dep = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not dep:
        raise NotFound(f"Deployment {deployment_id} not found")
    if not db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first():
        raise NotFound(f"Model {model_id} not found")
    load_model(model_id)
    for r in db.query(Rollout).filter(Rollout.deployment_id == deployment_id, Rollout.status == "active").all():
        finish_rollout(db, r, "cancelled", f"superseded by direct promotion of model {model_id}", actor=actor)
    previous = dep.model_id
    dep.model_id = model_id
    dep.endpoint = f"/deployments/{dep.id}/predict"
    _set_stage(db, model_id, "production")
    if previous != model_id:
        _set_stage(db, previous, "archived")
    record_event(db, "promoted", deployment_id=deployment_id, from_model_id=previous, to_model_id=model_id,
                 reason=reason, details={**(details or {}), "actor": actor, "mode": "direct"}, commit=False)
    db.commit()
    invalidate_route(deployment_id)


# ── Controller ───────────────────────────────────────────────────────────────

def _arm_stats(db, model_id: int, since: datetime) -> ArmStats:
    rows = (db.query(PredictionLog.status, PredictionLog.latency_ms, PredictionLog.prediction)
            .filter(PredictionLog.model_id == model_id, PredictionLog.created_at >= since)
            .order_by(PredictionLog.id.desc()).limit(EVAL_MAX_LOGS).all())
    stats = ArmStats()
    for status, latency, pred in rows:
        stats.requests += 1
        if status == "success":
            stats.latencies_ms.append(latency)
            stats.predictions.append(pred)
        else:
            stats.errors += 1
    return stats


def evaluate_once(db, rollout: Rollout) -> Dict[str, Any]:
    """Evaluate one active rollout and act on the decision. Returns the decision as a dict."""
    t = RolloutThresholds.from_dict(json.loads(rollout.thresholds_json or "{}"))
    stable = _arm_stats(db, rollout.stable_model_id, rollout.started_at)
    candidate = _arm_stats(db, rollout.candidate_model_id, rollout.started_at)
    decision = evaluate_rollout(stable, candidate, t)
    details = {"metrics": decision.metrics, "reasons": decision.reasons}

    if decision.action == "rollback":
        finish_rollout(db, rollout, "rolled_back", "; ".join(decision.reasons), details)
    elif decision.action == "promote" and rollout.mode == "shadow":
        res = db.execute(update(Rollout)
                         .where(Rollout.id == rollout.id, Rollout.status == "active", Rollout.mode == "shadow")
                         .values(mode="canary", traffic_percent=t.canary_percent_after_shadow,
                                 started_at=datetime.utcnow()))
        if res.rowcount == 1:
            record_event(db, "shadow_passed", deployment_id=rollout.deployment_id, rollout_id=rollout.id,
                         from_model_id=rollout.stable_model_id, to_model_id=rollout.candidate_model_id,
                         reason=f"shadow healthy; canary at {t.canary_percent_after_shadow:g}%",
                         details=details, commit=False)
            _set_stage(db, rollout.candidate_model_id, "canary")
        db.commit()
        invalidate_route(rollout.deployment_id)
    elif decision.action == "promote":
        finish_rollout(db, rollout, "promoted", "; ".join(decision.reasons), details)
    else:
        db.execute(update(Rollout).where(Rollout.id == rollout.id, Rollout.status == "active")
                   .values(last_metrics_json=json.dumps(decision.metrics)))
        db.commit()
    return decision.to_dict()


class RolloutController:
    def __init__(self, interval_s: float = EVAL_INTERVAL_S):
        self.interval_s = interval_s
        self._stop = threading.Event()
        self.last_run: Optional[float] = None
        self.last_error: Optional[str] = None

    def start(self):
        threading.Thread(target=self._loop, name="rollout-controller", daemon=True).start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.wait(self.interval_s):
            db = SessionLocal()
            try:
                for rollout in db.query(Rollout).filter(Rollout.status == "active").all():
                    evaluate_once(db, rollout)
                self.last_run, self.last_error = time.time(), None
            except Exception as e:
                db.rollback()
                self.last_error = repr(e)
                print("Rollout controller error:", repr(e))
            finally:
                db.close()


controller = RolloutController()
