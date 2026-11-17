"""v2 lifecycle routes: serve through a deployment, shadow/canary rollouts, events, feedback, policy."""

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from shared.database import SessionLocal
from shared.lifecycle.events import event_to_dict, load_policy, record_event, save_policy
from shared.models.deployment import Deployment
from shared.models.lifecycle import LabelledSample, LifecycleEvent, Rollout
from shared.models.monitoring import PredictionLog

from app.services import rollouts as svc
from app.services.logger import stats as logger_stats

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Schemas ──────────────────────────────────────────────────────────────────

class ServeRequest(BaseModel):
    features: Dict[str, Any]
    return_proba: bool = False


class RolloutRequest(BaseModel):
    candidate_model_id: int
    mode: str = Field("canary", description="shadow | canary")
    traffic_percent: float = 10.0
    thresholds: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    actor: str = "user"


class PromoteRequest(BaseModel):
    model_id: int
    reason: str = "manual promotion"
    details: Optional[Dict[str, Any]] = None
    actor: str = "user"


class Sample(BaseModel):
    features: Dict[str, Any]
    label: Any


class FeedbackRequest(BaseModel):
    samples: List[Sample]


class EventRequest(BaseModel):
    event_type: str
    rollout_id: Optional[int] = None
    from_model_id: Optional[int] = None
    to_model_id: Optional[int] = None
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


def _rollout_dict(r: Rollout) -> Dict[str, Any]:
    return {
        "id": r.id,
        "deployment_id": r.deployment_id,
        "stable_model_id": r.stable_model_id,
        "candidate_model_id": r.candidate_model_id,
        "mode": r.mode,
        "traffic_percent": r.traffic_percent,
        "status": r.status,
        "thresholds": json.loads(r.thresholds_json) if r.thresholds_json else None,
        "last_metrics": json.loads(r.last_metrics_json) if r.last_metrics_json else None,
        "decision_reason": r.decision_reason,
        "started_at": r.started_at.isoformat() + "Z" if r.started_at else None,
        "ended_at": r.ended_at.isoformat() + "Z" if r.ended_at else None,
    }


def _dep_or_404(db, deployment_id: int) -> Deployment:
    dep = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not dep:
        raise HTTPException(404, "Deployment not found")
    return dep


# ── Serving ──────────────────────────────────────────────────────────────────

@router.post("/deployments/{deployment_id}/predict")
def predict_via_deployment(deployment_id: int, request: ServeRequest):
    """Stable endpoint for clients: the deployment decides which model version answers."""
    try:
        return svc.serve(deployment_id, request.features, request.return_proba)
    except svc.NotFound as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"prediction failed: {e}")


# ── Rollouts ─────────────────────────────────────────────────────────────────

@router.post("/deployments/{deployment_id}/rollouts")
def create_rollout(deployment_id: int, request: RolloutRequest, db: Session = Depends(get_db)):
    try:
        r = svc.start_rollout(db, deployment_id, request.candidate_model_id, request.mode,
                              request.traffic_percent, request.thresholds, request.actor, request.reason)
    except svc.NotFound as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        raise HTTPException(400, f"candidate model could not be loaded: {e}")
    return _rollout_dict(r)


@router.get("/deployments/{deployment_id}/rollouts")
def list_rollouts(deployment_id: int, db: Session = Depends(get_db)):
    rows = db.query(Rollout).filter(Rollout.deployment_id == deployment_id).order_by(Rollout.id.desc()).all()
    return [_rollout_dict(r) for r in rows]


@router.get("/rollouts")
def list_all_rollouts(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Rollout)
    if status:
        q = q.filter(Rollout.status == status)
    return [_rollout_dict(r) for r in q.order_by(Rollout.id.desc()).limit(200).all()]


@router.get("/rollouts/{rollout_id}")
def get_rollout(rollout_id: int, db: Session = Depends(get_db)):
    r = db.query(Rollout).filter(Rollout.id == rollout_id).first()
    if not r:
        raise HTTPException(404, "Rollout not found")
    out = _rollout_dict(r)
    # What each arm actually served during the rollout, from the prediction logs.
    served = {}
    for arm, model_id in (("stable", r.stable_model_id), ("candidate", r.candidate_model_id)):
        q = db.query(PredictionLog.status).filter(PredictionLog.model_id == model_id,
                                                  PredictionLog.created_at >= r.started_at)
        if r.ended_at:
            q = q.filter(PredictionLog.created_at <= r.ended_at)
        statuses = [s for (s,) in q.all()]
        served[arm] = {"requests": len(statuses), "errors": sum(1 for s in statuses if s != "success")}
    out["served"] = served
    return out


@router.post("/rollouts/{rollout_id}/evaluate")
def evaluate_rollout_now(rollout_id: int, db: Session = Depends(get_db)):
    r = db.query(Rollout).filter(Rollout.id == rollout_id, Rollout.status == "active").first()
    if not r:
        raise HTTPException(404, "No active rollout with that id")
    return svc.evaluate_once(db, r)


@router.post("/rollouts/{rollout_id}/{action}")
def finish_rollout(rollout_id: int, action: str, reason: Optional[str] = None, db: Session = Depends(get_db)):
    outcome = {"promote": "promoted", "rollback": "rolled_back", "cancel": "cancelled"}.get(action)
    if not outcome:
        raise HTTPException(404, "action must be promote, rollback or cancel")
    r = db.query(Rollout).filter(Rollout.id == rollout_id).first()
    if not r:
        raise HTTPException(404, "Rollout not found")
    if not svc.finish_rollout(db, r, outcome, reason or f"manual {action}", actor="user"):
        raise HTTPException(409, f"rollout is already {r.status}")
    db.refresh(r)
    return _rollout_dict(r)


@router.post("/deployments/{deployment_id}/promote")
def promote(deployment_id: int, request: PromoteRequest, db: Session = Depends(get_db)):
    try:
        svc.promote_directly(db, deployment_id, request.model_id, request.reason, request.details, request.actor)
    except svc.NotFound as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(400, f"model could not be loaded: {e}")
    dep = _dep_or_404(db, deployment_id)
    return {"deployment_id": dep.id, "model_id": dep.model_id, "endpoint": dep.endpoint}


# ── Events ───────────────────────────────────────────────────────────────────

@router.get("/events")
def list_events(deployment_id: Optional[int] = None, limit: int = Query(100, le=1000),
                db: Session = Depends(get_db)):
    q = db.query(LifecycleEvent)
    if deployment_id is not None:
        q = q.filter(LifecycleEvent.deployment_id == deployment_id)
    return [event_to_dict(e) for e in q.order_by(LifecycleEvent.id.desc()).limit(limit).all()]


@router.get("/deployments/{deployment_id}/events")
def deployment_events(deployment_id: int, limit: int = Query(100, le=1000), db: Session = Depends(get_db)):
    return list_events(deployment_id, limit, db)


@router.post("/deployments/{deployment_id}/events")
def add_event(deployment_id: int, request: EventRequest, db: Session = Depends(get_db)):
    """Lets the monitoring and training services record drift / retrain / gate events."""
    _dep_or_404(db, deployment_id)
    e = record_event(db, request.event_type, deployment_id=deployment_id, rollout_id=request.rollout_id,
                     from_model_id=request.from_model_id, to_model_id=request.to_model_id,
                     reason=request.reason, details=request.details)
    return event_to_dict(e)


# ── Labelled feedback ────────────────────────────────────────────────────────

@router.post("/deployments/{deployment_id}/feedback")
def add_feedback(deployment_id: int, request: FeedbackRequest, db: Session = Depends(get_db)):
    """Ground truth for earlier predictions; drift-triggered retrains train on these rows."""
    _dep_or_404(db, deployment_id)
    db.add_all([LabelledSample(deployment_id=deployment_id, features_json=json.dumps(s.features),
                               label=json.dumps(s.label)) for s in request.samples])
    db.commit()
    total = db.query(LabelledSample).filter(LabelledSample.deployment_id == deployment_id).count()
    return {"accepted": len(request.samples), "total_labelled": total}


# ── Policy ───────────────────────────────────────────────────────────────────

@router.get("/deployments/{deployment_id}/policy")
def get_policy(deployment_id: int, db: Session = Depends(get_db)):
    _dep_or_404(db, deployment_id)
    return load_policy(db, deployment_id)


@router.put("/deployments/{deployment_id}/policy")
def put_policy(deployment_id: int, policy: Dict[str, Any], db: Session = Depends(get_db)):
    _dep_or_404(db, deployment_id)
    try:
        return save_policy(db, deployment_id, policy)
    except (TypeError, ValueError) as e:
        raise HTTPException(422, str(e))


# ── Ops ──────────────────────────────────────────────────────────────────────

@router.get("/lifecycle/status")
def lifecycle_status():
    c = svc.controller
    return {"controller_last_run": c.last_run, "controller_error": c.last_error,
            "eval_interval_s": c.interval_s, "logger": logger_stats()}
