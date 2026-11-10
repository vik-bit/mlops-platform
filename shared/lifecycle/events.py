"""Write and read lifecycle events and per-deployment policies (Postgres)."""

import json
from typing import Any, Dict, Optional

from shared.lifecycle.policy import GatePolicy, RetrainPolicy, RolloutThresholds
from shared.models.lifecycle import DeploymentPolicy, LifecycleEvent


def record_event(db, event_type: str, *, deployment_id: Optional[int] = None,
                 rollout_id: Optional[int] = None, from_model_id: Optional[int] = None,
                 to_model_id: Optional[int] = None, reason: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None, commit: bool = True) -> LifecycleEvent:
    event = LifecycleEvent(
        deployment_id=deployment_id,
        rollout_id=rollout_id,
        event_type=event_type,
        from_model_id=from_model_id,
        to_model_id=to_model_id,
        reason=reason,
        details_json=json.dumps(details, default=str) if details is not None else None,
    )
    db.add(event)
    if commit:
        db.commit()
    return event


def event_to_dict(e: LifecycleEvent) -> Dict[str, Any]:
    return {
        "id": e.id,
        "deployment_id": e.deployment_id,
        "rollout_id": e.rollout_id,
        "event_type": e.event_type,
        "from_model_id": e.from_model_id,
        "to_model_id": e.to_model_id,
        "reason": e.reason,
        "details": json.loads(e.details_json) if e.details_json else None,
        "created_at": e.created_at.isoformat() + "Z" if e.created_at else None,
    }


def load_policy(db, deployment_id: int) -> Dict[str, Any]:
    """Stored overrides merged over the defaults: {"retrain": {...}, "gate": {...}, "rollout": {...}}."""
    row = db.query(DeploymentPolicy).filter(DeploymentPolicy.deployment_id == deployment_id).first()
    stored = json.loads(row.policy_json) if row and row.policy_json else {}
    return {
        "retrain": RetrainPolicy.from_dict(stored.get("retrain")).to_dict(),
        "gate": GatePolicy.from_dict(stored.get("gate")).to_dict(),
        "rollout": RolloutThresholds.from_dict(stored.get("rollout")).to_dict(),
    }


def save_policy(db, deployment_id: int, policy: Dict[str, Any]) -> Dict[str, Any]:
    """Merge `policy` over what is stored, validate (unknown keys are dropped), store and return it."""
    merged = load_policy(db, deployment_id)
    for section in merged:
        merged[section].update(policy.get(section) or {})
    clean = {
        "retrain": RetrainPolicy.from_dict(merged["retrain"]).to_dict(),
        "gate": GatePolicy.from_dict(merged["gate"]).to_dict(),
        "rollout": RolloutThresholds.from_dict(merged["rollout"]).to_dict(),
    }
    row = db.query(DeploymentPolicy).filter(DeploymentPolicy.deployment_id == deployment_id).first()
    if row is None:
        row = DeploymentPolicy(deployment_id=deployment_id)
        db.add(row)
    row.policy_json = json.dumps(clean)
    db.commit()
    return clean
