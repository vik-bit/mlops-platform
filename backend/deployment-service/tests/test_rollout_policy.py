"""The pure rollout rules in shared/lifecycle/policy.py: routing, rollback triggers, promotion."""

import random

import pytest

from shared.lifecycle.policy import (
    ArmStats,
    RolloutThresholds,
    choose_arm,
    evaluate_rollout,
    percentile,
    prediction_psi,
)


def arm(n, errors=0, latency=10.0, preds=None):
    ok = n - errors
    if preds is None:
        preds = [0, 1] * (ok // 2) + [0] * (ok % 2)
    return ArmStats(requests=n, errors=errors, latencies_ms=[latency] * ok, predictions=list(preds))


T = RolloutThresholds(max_error_rate=0.05, max_p95_latency_ms=100, max_p95_ratio=3.0,
                      max_prediction_psi=0.25, min_requests=20)


# ── routing ─────────────────────────────────────────────────────────────────

def test_shadow_never_routes_to_candidate():
    assert {choose_arm("shadow", 100, r) for r in (0.0, 0.5, 0.999)} == {"stable"}


@pytest.mark.parametrize("pct", [0, 10, 50, 100])
def test_canary_share_matches_traffic_percent(pct):
    rng = random.Random(0)
    n = 20_000
    share = sum(choose_arm("canary", pct, rng.random()) == "candidate" for _ in range(n)) / n
    assert share == pytest.approx(pct / 100, abs=0.01)


def test_canary_percent_is_clamped():
    assert choose_arm("canary", 150, 0.99) == "candidate"
    assert choose_arm("canary", -5, 0.0) == "stable"


# ── evaluation ──────────────────────────────────────────────────────────────

def test_waits_for_min_requests_even_if_everything_failed():
    d = evaluate_rollout(arm(100), arm(19, errors=19), T)
    assert d.action == "continue"


def test_healthy_candidate_continues():
    d = evaluate_rollout(arm(200), arm(50), T)
    assert d.action == "continue" and d.reasons == ["healthy so far"]


def test_error_rate_above_threshold_rolls_back():
    d = evaluate_rollout(arm(200), arm(40, errors=3), T)  # 7.5% > 5%
    assert d.action == "rollback"
    assert any("error rate" in r for r in d.reasons)
    assert d.metrics["candidate_errors"] == 3


def test_error_rate_at_threshold_is_allowed():
    d = evaluate_rollout(arm(200), arm(40, errors=2), T)  # exactly 5%
    assert d.action == "continue"


def test_absolute_p95_latency_rolls_back():
    d = evaluate_rollout(arm(200, latency=5), arm(40, latency=150), T)
    assert d.action == "rollback"
    assert any("p95 latency 150 ms > 100 ms" in r for r in d.reasons)


def test_relative_p95_latency_rolls_back():
    d = evaluate_rollout(arm(200, latency=10), arm(40, latency=40), T)  # 4x stable, under 100 ms
    assert d.action == "rollback"
    assert any("x stable" in r for r in d.reasons)


def test_relative_latency_ignored_without_stable_data():
    d = evaluate_rollout(arm(5, latency=1), arm(40, latency=40), T)
    assert d.action == "continue"


def test_prediction_drift_rolls_back_constant_predictor():
    d = evaluate_rollout(arm(200), arm(40, preds=[1] * 40), T)
    assert d.action == "rollback"
    assert any("prediction PSI" in r for r in d.reasons)
    assert d.metrics["prediction_psi"] > 1


def test_all_breaches_are_reported():
    d = evaluate_rollout(arm(200), arm(40, errors=10, latency=500, preds=[1] * 30), T)
    assert d.action == "rollback" and len(d.reasons) == 4


def test_auto_promote_after_enough_healthy_requests():
    t = RolloutThresholds(min_requests=20, auto_promote=True, promote_after_requests=100)
    assert evaluate_rollout(arm(500), arm(99), t).action == "continue"
    assert evaluate_rollout(arm(500), arm(100), t).action == "promote"


def test_rollback_beats_promotion():
    t = RolloutThresholds(min_requests=20, auto_promote=True, promote_after_requests=100)
    assert evaluate_rollout(arm(500), arm(200, errors=50), t).action == "rollback"


def test_thresholds_from_dict_ignores_unknown_keys():
    t = RolloutThresholds.from_dict({"max_error_rate": 0.2, "bogus": 1, "min_requests": None})
    assert t.max_error_rate == 0.2 and t.min_requests == RolloutThresholds().min_requests


# ── helpers ─────────────────────────────────────────────────────────────────

def test_percentile():
    assert percentile([], 95) is None
    assert percentile(list(range(1, 101)), 95) == pytest.approx(95.05)


def test_prediction_psi_identical_is_zero_and_shift_is_large():
    rng = random.Random(1)
    ref = [rng.gauss(0, 1) for _ in range(2000)]
    same = [rng.gauss(0, 1) for _ in range(2000)]
    shifted = [rng.gauss(2, 1) for _ in range(2000)]
    assert prediction_psi(ref, same) < 0.05
    assert prediction_psi(ref, shifted) > 1.0


def test_prediction_psi_treats_logged_class_strings_as_categories():
    # Prediction logs store str(prediction), so classes arrive as "0"/"1".
    assert prediction_psi(["0", "1"] * 50, ["0", "1"] * 50) == pytest.approx(0, abs=1e-9)
    assert prediction_psi(["0", "1"] * 50, ["1"] * 100) > 1


def test_prediction_psi_empty():
    assert prediction_psi([], [1]) is None
