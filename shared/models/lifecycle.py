"""Tables for the v2 model lifecycle: rollouts, lifecycle events, labelled feedback and per-deployment policy.

All four are new tables, so `Base.metadata.create_all` creates them on an existing database
without touching the v1 tables.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text

from shared.database import Base


class Rollout(Base):
    """A candidate model being tried against a deployment's stable model."""

    __tablename__ = "rollouts"

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(Integer, nullable=False, index=True)
    stable_model_id = Column(Integer, nullable=False)
    candidate_model_id = Column(Integer, nullable=False)
    mode = Column(String, nullable=False)              # "shadow" | "canary"
    traffic_percent = Column(Float, default=0.0)       # canary share of live traffic
    status = Column(String, nullable=False, default="active")  # active | promoted | rolled_back | cancelled
    thresholds_json = Column(Text)                     # RolloutThresholds as JSON
    last_metrics_json = Column(Text)                   # latest evaluation, for the UI
    decision_reason = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime)


class LifecycleEvent(Base):
    """Append-only audit log: deploys, rollout starts, promotions, rollbacks, drift, retrains, gate results."""

    __tablename__ = "lifecycle_events"

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(Integer, index=True)
    rollout_id = Column(Integer)
    event_type = Column(String, nullable=False)
    from_model_id = Column(Integer)
    to_model_id = Column(Integer)
    reason = Column(Text)
    details_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class LabelledSample(Base):
    """Ground truth that arrived after a prediction: the features that were scored and the true label."""

    __tablename__ = "labelled_samples"

    id = Column(Integer, primary_key=True)
    deployment_id = Column(Integer, nullable=False)
    features_json = Column(Text, nullable=False)
    label = Column(Text, nullable=False)               # JSON-encoded, so numbers stay numbers
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_labelled_samples_dep_time", "deployment_id", "created_at"),)


class DeploymentPolicy(Base):
    """Per-deployment overrides for RetrainPolicy, GatePolicy and default RolloutThresholds (JSON)."""

    __tablename__ = "deployment_policies"

    deployment_id = Column(Integer, primary_key=True)
    policy_json = Column(Text, nullable=False, default="{}")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
