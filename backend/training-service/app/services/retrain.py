"""Drift-triggered retraining with a promotion gate.

1. Take the deployment's most recent `labelled_window` labelled samples, oldest -> newest.
2. Hold out the newest `holdout_fraction` (time-ordered: the candidate never sees the future).
3. Train a candidate with the live model's recipe (model type, hyperparameters, feature transforms).
4. Score the live model and the candidate on the same held-out rows.
5. `promotion_gate` decides; only a pass is handed to the deployment service (direct swap or canary).

Every step is recorded as a lifecycle event so the UI shows why a model was or was not promoted.
"""

import io
import json
import os
import time
from typing import Any, Dict, Optional

import joblib
import numpy as np
import pandas as pd
import requests
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error, r2_score

from shared.database import SessionLocal
from shared.lifecycle.events import load_policy, record_event
from shared.lifecycle.policy import GatePolicy, RetrainPolicy, promotion_gate, time_ordered_split
from shared.models.lifecycle import LabelledSample
from shared.models.model_registry import ModelRegistry
from shared.models.training_job import TrainingJob

from app.services.baseline import training_distribution
from app.services.model_saver import save_model
from app.services.trainer import train_model

DEPLOYMENT_SERVICE_URL = os.environ.get("DEPLOYMENT_SERVICE_URL", "http://deployment-service:8000")


def score(pipeline, X: pd.DataFrame, y: pd.Series, metric: str) -> Optional[float]:
    """`metric` of `pipeline` on (X, y); None if the pipeline cannot predict these rows."""
    try:
        pred = pipeline.predict(X)
    except Exception as e:
        print(f"scoring failed: {e!r}")
        return None
    if metric == "accuracy":
        return float(accuracy_score(y, pred))
    if metric == "f1":
        avg = "binary" if y.nunique() == 2 else "weighted"
        try:
            return float(f1_score(y, pred, average=avg, zero_division=0))
        except ValueError:
            return float(f1_score(y, pred, average="weighted", zero_division=0))
    if metric == "r2":
        return float(r2_score(y, pred))
    if metric == "rmse":
        return float(np.sqrt(mean_squared_error(y, pred)))
    if metric == "mae":
        return float(mean_absolute_error(y, pred))
    raise ValueError(f"unknown metric {metric}")


def load_labelled(db, deployment_id: int, window: int) -> pd.DataFrame:
    rows = (db.query(LabelledSample)
            .filter(LabelledSample.deployment_id == deployment_id)
            .order_by(LabelledSample.created_at.desc(), LabelledSample.id.desc())
            .limit(window).all())
    rows.reverse()  # oldest -> newest
    records = []
    for r in rows:
        rec = json.loads(r.features_json)
        rec["__label__"] = json.loads(r.label)
        records.append(rec)
    return pd.DataFrame.from_records(records)


def run_retrain(job_id: int, deployment_id: int, live_model_id: int, overrides: Dict[str, Any]):
    db = SessionLocal()
    t_start = time.time()
    try:
        job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
        job.status = "running"
        db.commit()

        policy = load_policy(db, deployment_id)
        retrain_p = RetrainPolicy.from_dict({**policy["retrain"], **(overrides.get("retrain") or {})})
        gate_p = GatePolicy.from_dict({**policy["gate"], **(overrides.get("gate") or {})})

        live = db.query(ModelRegistry).filter(ModelRegistry.id == live_model_id).first()
        if live is None or not live.metadata_json:
            raise ValueError(f"live model {live_model_id} has no metadata to copy the training recipe from")
        meta = json.loads(live.metadata_json)
        live_job = db.query(TrainingJob).filter(TrainingJob.id == live.training_job_id).first()
        target = live_job.target_column if live_job else meta.get("target_column")
        model_type = meta.get("model_type") or (live_job.model_type if live_job else "random_forest")
        task_type = meta.get("task_type") or (live_job.task_type if live_job else "classification")

        df = load_labelled(db, deployment_id, retrain_p.labelled_window)
        if len(df) < 2:
            raise ValueError(f"only {len(df)} labelled samples")
        df = df.rename(columns={"__label__": target})
        cut = time_ordered_split(len(df), retrain_p.holdout_fraction)
        train_df, hold_df = df.iloc[:cut], df.iloc[cut:]
        X_hold, y_hold = hold_df.drop(columns=[target]), hold_df[target]

        result = train_model(train_df, target, model_type=model_type, task_type=task_type,
                             hyperparameters=meta.get("hyperparameters"),
                             feature_transforms=meta.get("feature_transforms"))

        live_pipeline = joblib.load(io.BytesIO(live.model_data))
        live_score = score(live_pipeline, X_hold, y_hold, gate_p.metric)
        cand_score = score(result.pipeline, X_hold, y_hold, gate_p.metric)
        decision = promotion_gate(live_score, cand_score, len(hold_df), gate_p)

        X_train = train_df.drop(columns=[target])
        cand_meta = {
            "feature_importance": result.feature_importance,
            "model_type": model_type,
            "task_type": task_type,
            "target_column": target,
            "hyperparameters": meta.get("hyperparameters"),
            "feature_transforms": result.feature_transforms,
            "training_distribution": training_distribution(X_train),
            "training_rows": len(train_df),
            "retrain": {
                "deployment_id": deployment_id,
                "parent_model_id": live_model_id,
                "labelled_rows": len(df),
                "train_rows": len(train_df),
                "holdout_rows": len(hold_df),
                "gate": decision.to_dict(),
                "trigger": overrides.get("trigger"),
            },
        }
        candidate = ModelRegistry(
            training_job_id=job.id,
            model_name=f"{model_type}_model",
            model_version=f"retrain-of-{live_model_id}",
            model_data=save_model(result.pipeline, job_id),
            metadata_json=json.dumps(cand_meta, default=str),
            stage="candidate" if decision.passed else "rejected",
            accuracy=str(round(result.accuracy, 4)) if result.accuracy is not None else None,
        )
        db.add(candidate)
        job.status = "completed"
        job.accuracy, job.precision, job.recall, job.f1_score = result.accuracy, result.precision, result.recall, result.f1
        job.r2_score, job.mae, job.rmse = result.r2, result.mae, result.rmse
        job.cv_mean, job.cv_std = result.cv_mean, result.cv_std
        db.commit()
        db.refresh(candidate)

        details = {"job_id": job_id, "train_rows": len(train_df), "holdout_rows": len(hold_df),
                   "gate": decision.to_dict(), "seconds": round(time.time() - t_start, 2)}
        record_event(db, "gate_passed" if decision.passed else "gate_failed", deployment_id=deployment_id,
                     from_model_id=live_model_id, to_model_id=candidate.id, reason=decision.reason,
                     details=details)

        if decision.passed:
            try:
                _hand_to_deployment(deployment_id, candidate.id, retrain_p, decision.reason, details)
            except Exception as e:
                record_event(db, "promotion_failed", deployment_id=deployment_id, from_model_id=live_model_id,
                             to_model_id=candidate.id, reason=str(e), details={"job_id": job_id})
        print(f"[Retrain {job_id}] {decision.reason}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback()
        job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
        record_event(db, "retrain_failed", deployment_id=deployment_id, from_model_id=live_model_id,
                     reason=str(e), details={"job_id": job_id})
    finally:
        db.close()


def _hand_to_deployment(deployment_id: int, model_id: int, p: RetrainPolicy, reason: str, details: dict):
    if p.promote_mode == "canary":
        r = requests.post(f"{DEPLOYMENT_SERVICE_URL}/deployments/{deployment_id}/rollouts", timeout=60, json={
            "candidate_model_id": model_id, "mode": "canary", "traffic_percent": p.canary_percent,
            "actor": "retrain-gate", "reason": f"gate passed: {reason}"})
    else:
        r = requests.post(f"{DEPLOYMENT_SERVICE_URL}/deployments/{deployment_id}/promote", timeout=60, json={
            "model_id": model_id, "reason": f"gate passed: {reason}", "details": details,
            "actor": "retrain-gate"})
    if r.status_code >= 300:
        raise RuntimeError(f"deployment service refused the candidate: {r.status_code} {r.text[:300]}")
