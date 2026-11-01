import math

import numpy as np
import pandas as pd
import pytest

from app.services.drift import (
    _drift_level,
    _ks_test,
    _psi_categorical,
    _psi_numeric,
    compute_drift,
)


def numeric_baseline(values):
    """Build a baseline entry the same way training-service/app/routes/training.py does."""
    series = pd.Series(values)
    return {
        "type": "numeric",
        "mean": float(series.mean()),
        "std": float(series.std()),
        "hist_counts": [int(v) for v in pd.cut(series, bins=10).value_counts(sort=False).values],
        "hist_edges": [float(v) for v in pd.cut(series, bins=10, retbins=True)[1]],
    }


def categorical_baseline(values):
    vc = pd.Series(values).value_counts(normalize=True)
    return {"type": "categorical", "frequencies": {str(k): float(v) for k, v in vc.items()}}


@pytest.fixture
def rng():
    return np.random.default_rng(0)


# ── PSI ───────────────────────────────────────────────────────────────────────

def test_psi_numeric_matches_hand_computed_value():
    # Baseline 50/50 over two buckets, current 25/75:
    # (0.25-0.5)*ln(0.25/0.5) + (0.75-0.5)*ln(0.75/0.5) = 0.274653
    current = [0.5] * 25 + [1.5] * 75
    psi = _psi_numeric([50, 50], [0.0, 1.0, 2.0], current)
    assert psi == pytest.approx(0.25 * math.log(2) + 0.25 * math.log(1.5), abs=1e-6)


def test_psi_numeric_is_near_zero_for_same_distribution(rng):
    base = numeric_baseline(rng.normal(10, 2, 5000))
    current = rng.normal(10, 2, 2000).tolist()
    psi = _psi_numeric(base["hist_counts"], base["hist_edges"], current)
    assert psi < 0.02


def test_psi_numeric_counts_values_outside_training_range(rng):
    # The outer edges are widened to +-inf, so values beyond the training min/max
    # land in the end buckets instead of being silently dropped.
    base = numeric_baseline(rng.uniform(0, 1, 1000))
    psi = _psi_numeric(base["hist_counts"], base["hist_edges"], [5.0] * 100)
    assert psi > 1.0


def test_psi_categorical_new_category_is_high_drift():
    freq = {"a": 0.5, "b": 0.5}
    assert _psi_categorical(freq, ["a", "b"] * 50) == pytest.approx(0.0, abs=1e-9)
    assert _psi_categorical(freq, ["c"] * 100) > 0.2


def test_psi_categorical_empty_input_is_zero():
    assert _psi_categorical({"a": 1.0}, []) == 0.0


@pytest.mark.parametrize("psi,level", [
    (0.0, "none"), (0.099, "none"), (0.1, "moderate"), (0.199, "moderate"), (0.2, "high"),
])
def test_drift_level_thresholds(psi, level):
    assert _drift_level(psi) == level


# ── KS ────────────────────────────────────────────────────────────────────────

def test_ks_statistic_small_for_matching_normal(rng):
    ks = _ks_test({"mean": 0.0, "std": 1.0}, rng.normal(0, 1, 1000).tolist())
    assert ks is not None and ks < 0.05


def test_ks_statistic_large_for_shifted_normal(rng):
    ks = _ks_test({"mean": 0.0, "std": 1.0}, rng.normal(2, 1, 1000).tolist())
    assert ks > 0.5


def test_ks_skipped_for_tiny_sample_or_zero_std():
    assert _ks_test({"mean": 0.0, "std": 1.0}, [0.1, 0.2]) is None
    assert _ks_test({"mean": 0.0, "std": 0.0}, [0.0] * 10) is None


# ── compute_drift ─────────────────────────────────────────────────────────────

def test_compute_drift_no_drift(rng):
    baseline = {
        "age": numeric_baseline(rng.normal(40, 10, 5000)),
        "city": categorical_baseline(rng.choice(["x", "y", "z"], 5000, p=[0.5, 0.3, 0.2])),
    }
    current = {
        "age": rng.normal(40, 10, 500).tolist(),
        "city": rng.choice(["x", "y", "z"], 500, p=[0.5, 0.3, 0.2]).tolist(),
    }
    result = compute_drift(baseline, current)
    assert result["overall_drift"] == "none"
    assert result["drifted_features"] == []
    assert result["needs_retraining"] is False
    assert result["features"]["age"]["drift_level"] == "none"


def test_compute_drift_flags_shifted_feature(rng):
    baseline = {"age": numeric_baseline(rng.normal(40, 10, 5000))}
    result = compute_drift(baseline, {"age": rng.normal(60, 10, 500).tolist()})
    assert result["features"]["age"]["drift_level"] == "high"
    assert result["drifted_features"] == ["age"]
    assert result["needs_retraining"] is True


def test_compute_drift_insufficient_data_is_not_scored(rng):
    baseline = {"age": numeric_baseline(rng.normal(40, 10, 1000))}
    result = compute_drift(baseline, {"age": [40.0] * 10}, min_samples=30)
    assert result["features"]["age"] == {"status": "insufficient_data", "samples": 10, "required": 30}
    assert result["overall_drift"] == "unknown"
    assert result["overall_psi"] is None


def test_three_moderately_drifted_features_trigger_retraining(rng):
    # Each feature is shifted enough to be "moderate" but the mean PSI stays below 0.2,
    # so retraining is recommended by the ">= 3 drifted features" rule alone.
    baseline, current = {}, {}
    for name in ("f1", "f2", "f3"):
        baseline[name] = numeric_baseline(rng.normal(0, 1, 20000))
        current[name] = rng.normal(0.4, 1, 20000).tolist()
    result = compute_drift(baseline, current)
    assert all(result["features"][f]["drift_level"] == "moderate" for f in ("f1", "f2", "f3"))
    assert result["overall_drift"] == "moderate"
    assert result["needs_retraining"] is True

