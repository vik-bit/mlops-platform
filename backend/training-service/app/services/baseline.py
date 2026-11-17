"""The training-time feature distribution that drift detection compares live inputs against."""

import pandas as pd


def training_distribution(X: pd.DataFrame) -> dict:
    """Per-column baseline: 10-bin histogram + summary stats for numeric, frequencies for categorical."""
    dist = {}
    for col in X.columns:
        series = X[col].dropna()
        if pd.api.types.is_numeric_dtype(series):
            dist[col] = {
                "type":   "numeric",
                "mean":   round(float(series.mean()), 6),
                "std":    round(float(series.std()), 6),
                "min":    round(float(series.min()), 6),
                "max":    round(float(series.max()), 6),
                "p25":    round(float(series.quantile(0.25)), 6),
                "p50":    round(float(series.quantile(0.50)), 6),
                "p75":    round(float(series.quantile(0.75)), 6),
                "p95":    round(float(series.quantile(0.95)), 6),
                "hist_counts": [int(v) for v in
                                pd.cut(series, bins=10).value_counts(sort=False).values],
                "hist_edges":  [round(float(v), 6) for v in
                                pd.cut(series, bins=10, retbins=True)[1]],
            }
        else:
            vc = series.value_counts(normalize=True)
            dist[col] = {
                "type":        "categorical",
                "frequencies": {str(k): round(float(v), 6) for k, v in vc.items()},
            }
    return dist
