"""The rollout controller and serving path against a real (SQLite) database, no cluster.

Plants a candidate that cannot score live requests (it was trained with a column the clients do
not send), routes canary traffic, and checks that the controller rolls it back, records the
event once and sends traffic back to the stable model; and that a healthy candidate is promoted.
"""

import io
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from shared.database import Base, SessionLocal, engine
from shared.models.deployment import Deployment
from shared.models.lifecycle import LifecycleEvent
from shared.models.model_registry import ModelRegistry
from shared.models.monitoring import PredictionLog
from shared.models.training_job import TrainingJob  # noqa: F401  (FK target)

from app.services import rollouts


def _pipeline(columns, seed=0):
    rng = np.random.default_rng(seed)
    X = pd.DataFrame(rng.normal(size=(200, len(columns))), columns=columns)
    y = (X.iloc[:, 0] > 0).astype(int)
    return Pipeline([("scale", StandardScaler()), ("model", LogisticRegression())]).fit(X, y)


def _bytes(pipe):
    buf = io.BytesIO()
    joblib.dump(pipe, buf)
    return buf.getvalue()


@pytest.fixture
def db(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    rollouts.load_model.cache_clear()
    rollouts._routes.clear()

    # Log synchronously into the same DB instead of over HTTP to the monitoring service.
    def fake_log(model_id, input_data, prediction, latency_ms, status="success"):
        s = SessionLocal()
        s.add(PredictionLog(model_id=model_id, input_data=str(input_data), prediction=str(prediction),
                            latency_ms=latency_ms, status=status))
        s.commit()
        s.close()

    monkeypatch.setattr(rollouts, "log_prediction", fake_log)
    session = SessionLocal()
    yield session
    session.close()


def _setup(db, candidate_pipe):
    stable = ModelRegistry(model_name="stable", model_data=_bytes(_pipeline(["a", "b"])), stage="production")
    cand = ModelRegistry(model_name="cand", model_data=_bytes(candidate_pipe), stage="staging")
    db.add_all([stable, cand])
    db.commit()
    dep = Deployment(model_id=stable.id, status="active", endpoint=f"/predict/{stable.id}")
    db.add(dep)
    db.commit()
    return dep, stable, cand


def _traffic(dep_id, n, seed=0):
    rng = random.Random(seed)
    served = {"stable": 0, "candidate": 0, "errors": 0}
    for _ in range(n):
        try:
            out = rollouts.serve(dep_id, {"a": rng.gauss(0, 1), "b": rng.gauss(0, 1)})
            served[out["arm"]] += 1
        except Exception:
            served["errors"] += 1
    return served


def test_broken_canary_is_rolled_back_and_traffic_returns_to_stable(db):
    broken = _pipeline(["a", "b", "c"])  # expects a column live requests never carry
    dep, stable, cand = _setup(db, broken)
    r = rollouts.start_rollout(db, dep.id, cand.id, "canary", 50, {"min_requests": 20}, actor="test")

    served = _traffic(dep.id, 120)
    assert served["errors"] > 20 and served["candidate"] == 0  # every candidate request failed

    decision = rollouts.evaluate_once(db, r)
    assert decision["action"] == "rollback"
    assert any("error rate" in reason for reason in decision["reasons"])

    db.refresh(r)
    assert r.status == "rolled_back" and r.ended_at is not None
    assert db.get(ModelRegistry, cand.id).stage == "rejected"
    assert db.get(Deployment, dep.id).model_id == stable.id

    # A second evaluation (another replica) must not record a second rollback.
    assert rollouts.finish_rollout(db, r, "rolled_back", "again") is False
    events = [e.event_type for e in db.query(LifecycleEvent).order_by(LifecycleEvent.id)]
    assert events == ["canary_started", "rolled_back"]

    after = _traffic(dep.id, 50, seed=1)
    assert after == {"stable": 50, "candidate": 0, "errors": 0}


def test_shadow_results_are_logged_but_never_returned(db):
    dep, stable, cand = _setup(db, _pipeline(["a", "b"], seed=1))
    rollouts.start_rollout(db, dep.id, cand.id, "shadow", 0, None, actor="test")
    served = _traffic(dep.id, 30)
    assert served == {"stable": 30, "candidate": 0, "errors": 0}
    rollouts._shadow_pool.shutdown(wait=True)  # let the background shadow scorings finish
    rollouts._shadow_pool = ThreadPoolExecutor(max_workers=2)
    assert db.query(PredictionLog).filter(PredictionLog.model_id == cand.id).count() == 30


def test_healthy_canary_is_promoted(db):
    dep, stable, cand = _setup(db, _pipeline(["a", "b"], seed=2))
    r = rollouts.start_rollout(db, dep.id, cand.id, "canary", 50,
                               {"min_requests": 20, "auto_promote": True, "promote_after_requests": 40,
                                "max_p95_ratio": 100, "max_p95_latency_ms": 10_000}, actor="test")
    _traffic(dep.id, 200)
    assert rollouts.evaluate_once(db, r)["action"] == "promote"
    db.refresh(r)
    assert r.status == "promoted"
    assert db.get(Deployment, dep.id).model_id == cand.id
    assert db.get(ModelRegistry, stable.id).stage == "archived"
    assert _traffic(dep.id, 10)["stable"] == 10  # the candidate is now the stable model


def test_only_one_active_rollout_per_deployment(db):
    dep, stable, cand = _setup(db, _pipeline(["a", "b"], seed=3))
    rollouts.start_rollout(db, dep.id, cand.id, "canary", 10, None, actor="test")
    with pytest.raises(RuntimeError):
        rollouts.start_rollout(db, dep.id, cand.id, "canary", 10, None, actor="test")


def test_logs_from_before_the_rollout_are_ignored(db):
    dep, stable, cand = _setup(db, _pipeline(["a", "b"], seed=4))
    old = datetime.utcnow() - timedelta(hours=1)
    db.add_all([PredictionLog(model_id=cand.id, input_data="{}", prediction="x", latency_ms=1,
                              status="failed", created_at=old) for _ in range(50)])
    db.commit()
    r = rollouts.start_rollout(db, dep.id, cand.id, "canary", 50, {"min_requests": 20}, actor="test")
    assert rollouts.evaluate_once(db, r)["action"] == "continue"
