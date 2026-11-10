"""The drift -> retrain decision: real compute_drift output fed to shared/lifecycle/policy.should_retrain."""

import numpy as np
import pandas as pd
import pytest

from app.services.drift import compute_drift
from shared.lifecycle.policy import RetrainPolicy, drift_breaches, should_retrain


def baseline(values):
    s = pd.Series(values)
    return {
        "type": "numeric",
        "mean": float(s.mean()),
        "std": float(s.std()),
        "hist_counts": [int(v) for v in pd.cut(s, bins=10).value_counts(sort=False).values],
        "hist_edges": [float(v) for v in pd.cut(s, bins=10, retbins=True)[1]],
    }


@pytest.fixture
def reports():
    rng = np.random.default_rng(0)
    base = {"x": baseline(rng.normal(0, 1, 5000)), "y": baseline(rng.normal(5, 2, 5000))}
    same = compute_drift(base, {"x": list(rng.normal(0, 1, 500)), "y": list(rng.normal(5, 2, 500))})
    shifted = compute_drift(base, {"x": list(rng.normal(1.5, 1, 500)), "y": list(rng.normal(5, 2, 500))})
    return same, shifted


P = RetrainPolicy(enabled=True, psi_threshold=0.2, feature_psi_threshold=0.25, ks_threshold=0.3,
                  min_labelled=100, cooldown_s=600)
KW = dict(labelled_count=500, retrain_in_flight=False, last_retrain_at=None, now=10_000.0)


def test_no_drift_no_retrain(reports):
    same, _ = reports
    d = should_retrain(same, P, **KW)
    assert not d.retrain and d.breaches == []


def test_covariate_shift_triggers_retrain(reports):
    _, shifted = reports
    d = should_retrain(shifted, P, **KW)
    assert d.retrain
    assert any(b.startswith("x: PSI") for b in d.breaches)
    assert any(b.startswith("x: KS") for b in d.breaches)
    assert not any(b.startswith("y:") for b in d.breaches)


def test_disabled_policy_never_retrains(reports):
    _, shifted = reports
    d = should_retrain(shifted, RetrainPolicy(enabled=False), **KW)
    assert not d.retrain and "disabled" in d.reason


def test_cooldown_blocks_then_expires(reports):
    _, shifted = reports
    blocked = should_retrain(shifted, P, **{**KW, "last_retrain_at": 10_000.0 - 100})
    assert not blocked.retrain and "cooldown" in blocked.reason
    assert should_retrain(shifted, P, **{**KW, "last_retrain_at": 10_000.0 - 601}).retrain


def test_in_flight_retrain_blocks(reports):
    _, shifted = reports
    assert not should_retrain(shifted, P, **{**KW, "retrain_in_flight": True}).retrain


def test_needs_enough_labelled_samples(reports):
    _, shifted = reports
    d = should_retrain(shifted, P, **{**KW, "labelled_count": 99})
    assert not d.retrain and "labelled" in d.reason and d.breaches


def test_insufficient_data_features_do_not_breach():
    rng = np.random.default_rng(1)
    report = compute_drift({"x": baseline(rng.normal(0, 1, 1000))}, {"x": [100.0] * 10}, min_samples=30)
    assert drift_breaches(report, P) == []


def test_ks_alone_can_trigger():
    report = {"overall_psi": 0.05, "features": {"x": {"psi": 0.1, "ks_statistic": 0.45}}}
    assert drift_breaches(report, P) == ["x: KS 0.450 > 0.3"]
