"""The promotion gate (shared/lifecycle/policy.py) and the scoring/split it relies on."""

import numpy as np
import pandas as pd
import pytest

from shared.lifecycle.policy import GatePolicy, promotion_gate, time_ordered_split


# ── gate ────────────────────────────────────────────────────────────────────

def test_better_candidate_passes():
    d = promotion_gate(0.80, 0.85, 200, GatePolicy(metric="accuracy", margin=0.0))
    assert d.passed and d.delta == pytest.approx(0.05)


def test_slightly_worse_within_margin_passes():
    assert promotion_gate(0.80, 0.795, 200, GatePolicy(metric="accuracy", margin=0.01)).passed


def test_worse_beyond_margin_fails():
    d = promotion_gate(0.80, 0.78, 200, GatePolicy(metric="accuracy", margin=0.01))
    assert not d.passed and d.delta == pytest.approx(-0.02)
    assert "worse" in d.reason


def test_equal_score_passes_with_zero_margin():
    assert promotion_gate(0.8, 0.8, 200, GatePolicy(metric="f1", margin=0.0)).passed


@pytest.mark.parametrize("live,cand,passed", [(10.0, 9.0, True), (10.0, 10.4, True), (10.0, 11.0, False)])
def test_lower_is_better_metrics(live, cand, passed):
    d = promotion_gate(live, cand, 200, GatePolicy(metric="rmse", margin=0.5))
    assert d.passed is passed
    assert d.delta == pytest.approx(live - cand)  # positive = candidate better


def test_too_small_holdout_fails_even_if_better():
    d = promotion_gate(0.5, 0.99, 10, GatePolicy(min_holdout=50))
    assert not d.passed and "held-out" in d.reason


def test_unscorable_candidate_fails():
    assert not promotion_gate(0.8, None, 200, GatePolicy()).passed
    assert not promotion_gate(0.8, float("nan"), 200, GatePolicy()).passed


def test_unscorable_live_model_lets_candidate_through():
    d = promotion_gate(None, 0.7, 200, GatePolicy())
    assert d.passed and d.delta is None


def test_unknown_metric_is_rejected():
    with pytest.raises(ValueError):
        promotion_gate(1, 1, 100, GatePolicy(metric="auc"))


# ── time-ordered split ──────────────────────────────────────────────────────

@pytest.mark.parametrize("n,frac,cut", [(100, 0.3, 70), (10, 0.25, 8), (2, 0.5, 1), (5, 0.0, 4), (5, 1.0, 1)])
def test_time_ordered_split_holds_out_the_newest_rows(n, frac, cut):
    assert time_ordered_split(n, frac) == cut


def test_split_needs_two_rows():
    with pytest.raises(ValueError):
        time_ordered_split(1, 0.3)


# ── scoring used by the retrain job ─────────────────────────────────────────

def test_score_returns_none_when_live_model_cannot_handle_rows():
    from app.services.retrain import score

    class Broken:
        def predict(self, X):
            raise KeyError("column missing")

    X = pd.DataFrame({"a": [1, 2]})
    assert score(Broken(), X, pd.Series([0, 1]), "accuracy") is None


def test_score_metrics():
    from app.services.retrain import score

    class Echo:
        def predict(self, X):
            return X["a"].to_numpy()

    X = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0]})
    y = pd.Series([1.0, 2.0, 3.0, 6.0])
    assert score(Echo(), X, y, "mae") == pytest.approx(0.5)
    assert score(Echo(), X, y, "rmse") == pytest.approx(1.0)
    assert score(Echo(), X, pd.Series([1.0, 2.0, 0.0, 4.0]), "accuracy") == pytest.approx(0.75)


def test_baseline_matches_drift_input_format():
    from app.services.baseline import training_distribution

    rng = np.random.default_rng(0)
    X = pd.DataFrame({"num": rng.normal(size=100), "cat": rng.choice(["x", "y"], size=100)})
    dist = training_distribution(X)
    assert dist["num"]["type"] == "numeric" and len(dist["num"]["hist_edges"]) == 11
    assert sum(dist["num"]["hist_counts"]) == 100
    assert set(dist["cat"]["frequencies"]) == {"x", "y"}
