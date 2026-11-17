"""Pure decision logic for safe rollouts and drift-triggered retraining.

Nothing here touches the database, the network or the clock (callers pass `now`), so every rule
can be tested on plain numbers.

Three decisions live here:

* `evaluate_rollout`  - keep a shadow/canary running, roll it back, or promote it.
* `promotion_gate`    - may a retrained candidate replace the live model?
* `should_retrain`    - does a drift report justify queueing a retrain?
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

# ── Shared helpers ────────────────────────────────────────────────────────────


def _from_dict(cls, data: Optional[Dict[str, Any]]):
    """Build a dataclass from a dict, ignoring unknown keys (policies are stored as JSON)."""
    data = data or {}
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in names and v is not None})


def percentile(values: Sequence[float], q: float) -> Optional[float]:
    """q-th percentile (0-100) with linear interpolation; None for no data."""
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=float), q))


def _is_number(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return math.isfinite(v)
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def prediction_psi(reference: Sequence[Any], current: Sequence[Any], bins: int = 10) -> Optional[float]:
    """Population Stability Index of the candidate's predictions against the stable model's.

    Categorical (class labels): PSI over class frequencies.
    Numeric (regression outputs): PSI over `bins` quantile buckets of the reference.
    Returns None when either side is empty.

    Bin counts are Laplace-smoothed (+0.5) rather than floored at 1e-6 as in drift.py: with a
    small candidate sample many bins are legitimately empty, and a 1e-6 floor adds ~1.15 PSI per
    empty bin, which rolled back a healthy canary on its first 23 predictions (docs/v2-results).
    """
    if not reference or not current:
        return None

    numeric = all(_is_number(v) for v in reference) and all(_is_number(v) for v in current)
    # A handful of distinct integer values (class ids) is still a categorical output.
    if numeric and len(set(map(float, reference))) <= 20:
        numeric = False

    if numeric:
        ref = np.asarray(reference, dtype=float)
        cur = np.asarray(current, dtype=float)
        edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
        if len(edges) < 2:
            edges = np.array([ref.min() - 0.5, ref.min() + 0.5])
        edges[0], edges[-1] = -np.inf, np.inf
        ref_n = np.histogram(ref, bins=edges)[0].astype(float)
        cur_n = np.histogram(cur, bins=edges)[0].astype(float)
    else:
        ref_s = [str(v) for v in reference]
        cur_s = [str(v) for v in current]
        cats = sorted(set(ref_s) | set(cur_s))
        ref_n = np.array([ref_s.count(c) for c in cats], dtype=float)
        cur_n = np.array([cur_s.count(c) for c in cats], dtype=float)

    ref_pct = (ref_n + 0.5) / (ref_n.sum() + 0.5 * len(ref_n))
    cur_pct = (cur_n + 0.5) / (cur_n.sum() + 0.5 * len(cur_n))
    return round(float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))), 6)


# ── Traffic routing ───────────────────────────────────────────────────────────


def choose_arm(mode: str, traffic_percent: float, rnd: Optional[float] = None) -> str:
    """Which model answers this request: "stable" or "candidate".

    shadow -> always "stable" (the candidate is scored on the side, never returned).
    canary -> "candidate" for `traffic_percent`% of requests, chosen independently per request.
    """
    if mode != "canary":
        return "stable"
    pct = min(max(float(traffic_percent), 0.0), 100.0)
    r = random.random() if rnd is None else rnd
    return "candidate" if r * 100.0 < pct else "stable"


# ── Rollout evaluation ────────────────────────────────────────────────────────


@dataclass
class RolloutThresholds:
    """When to abort a shadow/canary rollout, and when it has earned promotion.

    max_error_rate          candidate errors / candidate requests
    max_p95_latency_ms      absolute ceiling on the candidate's p95 inference latency
    max_p95_ratio           candidate p95 / stable p95 (ignored until the stable arm has data)
    max_prediction_psi      PSI of candidate predictions vs stable predictions on the same window
    min_requests            candidate requests needed before any rule may fire
    min_psi_samples         candidate predictions needed before the prediction-PSI rule may fire
                            (PSI is noisy on small samples; see prediction_psi)
    auto_promote            promote once `promote_after_requests` healthy candidate requests are seen
    promote_after_requests  (shadow promotes to canary at `canary_percent_after_shadow`)
    """

    max_error_rate: float = 0.05
    max_p95_latency_ms: float = 500.0
    max_p95_ratio: float = 3.0
    max_prediction_psi: float = 0.25
    min_requests: int = 20
    min_psi_samples: int = 200
    auto_promote: bool = False
    promote_after_requests: int = 300
    canary_percent_after_shadow: float = 10.0

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "RolloutThresholds":
        return _from_dict(cls, data)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArmStats:
    """What one arm (stable or candidate) did during the rollout window."""

    requests: int = 0
    errors: int = 0
    latencies_ms: List[float] = field(default_factory=list)
    predictions: List[Any] = field(default_factory=list)

    @property
    def error_rate(self) -> Optional[float]:
        return self.errors / self.requests if self.requests else None

    @property
    def p95_ms(self) -> Optional[float]:
        return percentile(self.latencies_ms, 95)


@dataclass
class RolloutDecision:
    action: str  # "continue" | "rollback" | "promote"
    reasons: List[str]
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_rollout(stable: ArmStats, candidate: ArmStats, t: RolloutThresholds) -> RolloutDecision:
    """Decide what to do with a running rollout. Every breached rule is reported, not just the first."""
    p95_c, p95_s = candidate.p95_ms, stable.p95_ms
    psi = prediction_psi(stable.predictions, candidate.predictions)
    metrics = {
        "stable_requests": stable.requests,
        "candidate_requests": candidate.requests,
        "candidate_errors": candidate.errors,
        "candidate_error_rate": None if candidate.error_rate is None else round(candidate.error_rate, 4),
        "stable_error_rate": None if stable.error_rate is None else round(stable.error_rate, 4),
        "candidate_p95_ms": None if p95_c is None else round(p95_c, 2),
        "stable_p95_ms": None if p95_s is None else round(p95_s, 2),
        "prediction_psi": psi,
    }

    if candidate.requests < t.min_requests:
        return RolloutDecision("continue", [f"waiting for {t.min_requests} candidate requests"], metrics)

    reasons = []
    if candidate.error_rate is not None and candidate.error_rate > t.max_error_rate:
        reasons.append(f"error rate {candidate.error_rate:.1%} > {t.max_error_rate:.1%}")
    if p95_c is not None and p95_c > t.max_p95_latency_ms:
        reasons.append(f"p95 latency {p95_c:.0f} ms > {t.max_p95_latency_ms:.0f} ms")
    if p95_c is not None and p95_s and len(stable.latencies_ms) >= t.min_requests:
        if p95_c > t.max_p95_ratio * p95_s:
            reasons.append(f"p95 latency {p95_c:.0f} ms > {t.max_p95_ratio:g}x stable ({p95_s:.0f} ms)")
    if (psi is not None and len(candidate.predictions) >= t.min_psi_samples
            and len(stable.predictions) >= t.min_psi_samples and psi > t.max_prediction_psi):
        reasons.append(f"prediction PSI {psi:.3f} > {t.max_prediction_psi}")

    if reasons:
        return RolloutDecision("rollback", reasons, metrics)
    if t.auto_promote and candidate.requests >= t.promote_after_requests:
        return RolloutDecision("promote", [f"{candidate.requests} healthy candidate requests"], metrics)
    return RolloutDecision("continue", ["healthy so far"], metrics)


# ── Promotion gate ────────────────────────────────────────────────────────────

HIGHER_IS_BETTER = {"accuracy": True, "f1": True, "r2": True, "rmse": False, "mae": False}


@dataclass
class GatePolicy:
    """A retrained candidate replaces the live model only if, on the same held-out set,
    its `metric` is not worse than the live model's by more than `margin` (absolute units).
    `min_holdout` rows are required for the comparison to count at all."""

    metric: str = "accuracy"
    margin: float = 0.0
    min_holdout: int = 50

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "GatePolicy":
        return _from_dict(cls, data)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GateDecision:
    passed: bool
    reason: str
    metric: str
    live_score: Optional[float]
    candidate_score: Optional[float]
    delta: Optional[float]  # candidate - live, signed so that > 0 means "candidate is better"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def promotion_gate(live_score: Optional[float], candidate_score: Optional[float],
                   holdout_rows: int, policy: GatePolicy) -> GateDecision:
    if policy.metric not in HIGHER_IS_BETTER:
        raise ValueError(f"unknown gate metric {policy.metric!r}; use one of {sorted(HIGHER_IS_BETTER)}")
    if holdout_rows < policy.min_holdout:
        return GateDecision(False, f"held-out set has {holdout_rows} rows < {policy.min_holdout}",
                            policy.metric, live_score, candidate_score, None)
    if candidate_score is None or not math.isfinite(candidate_score):
        return GateDecision(False, "candidate could not be scored", policy.metric,
                            live_score, candidate_score, None)
    if live_score is None or not math.isfinite(live_score):
        # The live model failed on the held-out data (e.g. it cannot handle the new inputs).
        return GateDecision(True, "live model could not be scored on the held-out set", policy.metric,
                            live_score, candidate_score, None)

    sign = 1.0 if HIGHER_IS_BETTER[policy.metric] else -1.0
    delta = sign * (candidate_score - live_score)
    passed = delta >= -policy.margin
    verdict = "not worse" if passed else "worse"
    reason = (f"candidate {policy.metric} {candidate_score:.4f} vs live {live_score:.4f}: "
              f"{verdict} than live beyond margin {policy.margin:g}")
    return GateDecision(passed, reason, policy.metric, live_score, candidate_score, round(delta, 6))


# ── Retrain trigger ───────────────────────────────────────────────────────────


@dataclass
class RetrainPolicy:
    """When drift on a deployment should queue a retrain.

    Fires when the overall PSI, or any single feature's PSI or KS statistic, crosses its threshold,
    there are at least `min_labelled` labelled samples to train on, no retrain for this deployment
    is already running, and `cooldown_s` has passed since the last one.
    """

    enabled: bool = False
    psi_threshold: float = 0.2
    feature_psi_threshold: float = 0.25
    ks_threshold: float = 0.3
    window: int = 500            # recent prediction logs to compare against the training baseline
    min_samples: int = 100       # per-feature, passed to compute_drift
    min_labelled: int = 300
    labelled_window: int = 2000  # most recent labelled rows used for retrain + held-out set
    holdout_fraction: float = 0.3
    cooldown_s: float = 600.0
    promote_mode: str = "direct"  # "direct" or "canary"
    canary_percent: float = 10.0

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "RetrainPolicy":
        return _from_dict(cls, data)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def drift_breaches(drift: Dict[str, Any], policy: RetrainPolicy) -> List[str]:
    """The threshold breaches in a `compute_drift` report (empty list = no breach)."""
    breaches = []
    overall = drift.get("overall_psi")
    if overall is not None and overall > policy.psi_threshold:
        breaches.append(f"overall PSI {overall:.3f} > {policy.psi_threshold}")
    for name, feat in sorted((drift.get("features") or {}).items()):
        psi = feat.get("psi")
        ks = feat.get("ks_statistic")
        if psi is not None and psi > policy.feature_psi_threshold:
            breaches.append(f"{name}: PSI {psi:.3f} > {policy.feature_psi_threshold}")
        if ks is not None and ks > policy.ks_threshold:
            breaches.append(f"{name}: KS {ks:.3f} > {policy.ks_threshold}")
    return breaches


@dataclass
class RetrainDecision:
    retrain: bool
    reason: str
    breaches: List[str]


def should_retrain(drift: Dict[str, Any], policy: RetrainPolicy, *, labelled_count: int,
                   retrain_in_flight: bool, last_retrain_at: Optional[float], now: float) -> RetrainDecision:
    if not policy.enabled:
        return RetrainDecision(False, "retraining disabled for this deployment", [])
    breaches = drift_breaches(drift, policy)
    if not breaches:
        return RetrainDecision(False, "no drift threshold crossed", [])
    if retrain_in_flight:
        return RetrainDecision(False, "a retrain is already running", breaches)
    if last_retrain_at is not None and now - last_retrain_at < policy.cooldown_s:
        left = policy.cooldown_s - (now - last_retrain_at)
        return RetrainDecision(False, f"cooldown: {left:.0f} s left", breaches)
    if labelled_count < policy.min_labelled:
        return RetrainDecision(False, f"only {labelled_count} labelled samples < {policy.min_labelled}", breaches)
    return RetrainDecision(True, "drift threshold crossed", breaches)


def time_ordered_split(n_rows: int, holdout_fraction: float) -> int:
    """Index where the held-out tail starts for rows sorted oldest -> newest.

    The newest rows are held out, so the candidate is judged on data that arrived after
    everything it trained on (no look-ahead). Always leaves at least one row on each side.
    """
    if n_rows < 2:
        raise ValueError("need at least 2 rows to split")
    frac = min(max(holdout_fraction, 0.0), 1.0)
    n_hold = min(max(int(round(n_rows * frac)), 1), n_rows - 1)
    return n_rows - n_hold
