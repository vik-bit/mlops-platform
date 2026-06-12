"""
Drift detection service.

compute_drift(baseline, current_df) compares current input distributions
against the training baseline stored in metadata.

Methods:
  Numeric  → PSI (Population Stability Index) + KS test
  Categorical → Chi-squared distance on frequency tables

PSI thresholds (industry standard):
  < 0.1  → No significant drift (green)
  0.1–0.2 → Moderate drift — monitor (amber)
  > 0.2  → Significant drift — consider retraining (red)
"""

import json
import numpy as np
from typing import Any, Dict, Optional

try:
    from scipy import stats as scipy_stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


# ── PSI ───────────────────────────────────────────────────────────────────────

def _psi_numeric(
    baseline_counts: list,
    baseline_edges: list,
    current_values: list,
) -> float:
    """
    Population Stability Index for a numeric feature.
    Uses the training histogram bins as reference buckets.
    """
    edges = np.array(baseline_edges)
    baseline = np.array(baseline_counts, dtype=float)

    # Extend edges slightly to capture out-of-range values
    edges[0]  = -np.inf
    edges[-1] =  np.inf

    current_counts, _ = np.histogram(current_values, bins=edges)
    current = current_counts.astype(float)

    # Normalise to proportions
    baseline_pct = baseline / baseline.sum() if baseline.sum() > 0 else baseline
    current_pct  = current  / current.sum()  if current.sum()  > 0 else current

    # Replace zeros to avoid log(0)
    baseline_pct = np.where(baseline_pct == 0, 1e-6, baseline_pct)
    current_pct  = np.where(current_pct  == 0, 1e-6, current_pct)

    psi = np.sum((current_pct - baseline_pct) * np.log(current_pct / baseline_pct))
    return round(float(psi), 6)


def _psi_categorical(
    baseline_freq: dict,
    current_values: list,
) -> float:
    """PSI for a categorical feature."""
    total = len(current_values)
    if total == 0:
        return 0.0

    current_counts: Dict[str, int] = {}
    for v in current_values:
        key = str(v)
        current_counts[key] = current_counts.get(key, 0) + 1

    all_cats = set(baseline_freq.keys()) | set(current_counts.keys())
    psi = 0.0
    for cat in all_cats:
        b = baseline_freq.get(cat, 1e-6)
        c = current_counts.get(cat, 0) / total if total > 0 else 1e-6
        if c == 0:
            c = 1e-6
        psi += (c - b) * np.log(c / b)

    return round(float(psi), 6)


def _ks_test(baseline_stats: dict, current_values: list) -> Optional[float]:
    """KS statistic for numeric feature using baseline mean/std as normal reference."""
    if not SCIPY_AVAILABLE or len(current_values) < 5:
        return None
    try:
        mean = baseline_stats["mean"]
        std  = baseline_stats["std"]
        if std == 0:
            return None
        ks_stat, _ = scipy_stats.kstest(
            current_values,
            "norm",
            args=(mean, std),
        )
        return round(float(ks_stat), 6)
    except Exception:
        return None


def _drift_level(psi: float) -> str:
    if psi < 0.1:
        return "none"
    elif psi < 0.2:
        return "moderate"
    else:
        return "high"


# ── Main function ─────────────────────────────────────────────────────────────

def compute_drift(
    baseline: Dict[str, Any],
    current_data: Dict[str, list],
    min_samples: int = 30,
) -> Dict[str, Any]:
    """
    Compare current input distributions against training baseline.

    baseline:     the `training_distribution` dict from _metadata.json
    current_data: {feature_name: [list of recent values]} from prediction logs
    min_samples:  minimum number of recent predictions required for drift analysis

    Returns per-feature drift scores and an overall platform drift signal.
    """
    results = {}
    overall_psi_values = []

    for feature, base_stats in baseline.items():
        current_values = current_data.get(feature, [])

        if len(current_values) < min_samples:
            results[feature] = {
                "status":   "insufficient_data",
                "samples":  len(current_values),
                "required": min_samples,
            }
            continue

        feat_type = base_stats.get("type", "numeric")

        if feat_type == "numeric":
            hist_counts = base_stats.get("hist_counts")
            hist_edges  = base_stats.get("hist_edges")

            if hist_counts and hist_edges:
                psi = _psi_numeric(hist_counts, hist_edges, current_values)
            else:
                psi = 0.0

            ks = _ks_test(base_stats, current_values)

            results[feature] = {
                "type":          "numeric",
                "psi":           psi,
                "drift_level":   _drift_level(psi),
                "ks_statistic":  ks,
                "samples":       len(current_values),
                "current_mean":  round(float(np.mean(current_values)), 4),
                "current_std":   round(float(np.std(current_values)), 4),
                "baseline_mean": base_stats.get("mean"),
                "baseline_std":  base_stats.get("std"),
            }
            overall_psi_values.append(psi)

        elif feat_type == "categorical":
            freq = base_stats.get("frequencies", {})
            psi  = _psi_categorical(freq, current_values)

            current_freq: Dict[str, float] = {}
            total = len(current_values)
            for v in current_values:
                k = str(v)
                current_freq[k] = current_freq.get(k, 0) + 1
            current_freq = {k: round(v / total, 6) for k, v in current_freq.items()}

            results[feature] = {
                "type":              "categorical",
                "psi":               psi,
                "drift_level":       _drift_level(psi),
                "samples":           len(current_values),
                "current_freq":      current_freq,
                "baseline_freq":     freq,
            }
            overall_psi_values.append(psi)

    # Overall drift signal
    if not overall_psi_values:
        overall_drift = "unknown"
        overall_psi   = None
    else:
        overall_psi   = round(float(np.mean(overall_psi_values)), 6)
        overall_drift = _drift_level(overall_psi)

    drifted_features = [f for f, r in results.items()
                        if r.get("drift_level") in ("moderate", "high")]

    return {
        "overall_psi":       overall_psi,
        "overall_drift":     overall_drift,
        "drifted_features":  drifted_features,
        "needs_retraining":  overall_drift == "high" or len(drifted_features) >= 3,
        "features":          results,
    }