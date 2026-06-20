import pandas as pd
import numpy as np
from typing import Optional


def profile_dataset(path: str, target_column: Optional[str] = None) -> dict:
    """
    Full dataset profile. Called by GET /datasets/{id}/profile.

    Returns columns as a dict keyed by column name so the frontend can do
    Object.entries(profile.columns) directly.
    """
    df = pd.read_csv(path)

    n_rows, n_cols = df.shape
    total_cells    = n_rows * n_cols
    missing_cells  = int(df.isnull().sum().sum())

    # ── Per-column profiles — keyed by name ──────────────────────────────────
    columns: dict = {}
    for col in df.columns:
        series    = df[col]
        dtype     = str(series.dtype)
        n_missing = int(series.isnull().sum())
        n_unique  = int(series.nunique())
        missing_pct = round(n_missing / n_rows * 100, 2) if n_rows else 0

        col_info: dict = {
            "dtype":       dtype,
            "missing":     n_missing,
            "missing_pct": missing_pct,
            "unique_count": n_unique,
        }

        if pd.api.types.is_numeric_dtype(series):
            col_info.update({
                "min":    _safe(series.min()),
                "max":    _safe(series.max()),
                "mean":   _safe(series.mean()),
                "std":    _safe(series.std()),
                "median": _safe(series.median()),
            })
        else:
            top = series.value_counts().head(5)
            col_info["top_values"] = [str(k) for k in top.index.tolist()]

        columns[col] = col_info

    # ── Target analysis ───────────────────────────────────────────────────────
    target_info = None
    warnings    = []

    if target_column:
        if target_column not in df.columns:
            warnings.append(f"Target column '{target_column}' not found in dataset")
        else:
            t            = df[target_column]
            value_counts = t.value_counts()
            n_classes    = int(t.nunique())
            is_numeric   = pd.api.types.is_numeric_dtype(t)

            target_info = {
                "column":       target_column,
                "dtype":        str(t.dtype),
                "n_unique":     n_classes,
                "missing":      int(t.isnull().sum()),
                "missing_pct":  round(t.isnull().sum() / n_rows * 100, 2),
                "distribution": {str(k): int(v) for k, v in value_counts.items()},
                "suggested_task": "regression" if (
                    is_numeric and n_classes > 20
                ) else "classification",
            }

            # Class imbalance check
            if 2 <= n_classes <= 20:
                counts = value_counts.values
                ratio  = counts.max() / counts.min() if counts.min() > 0 else float("inf")
                if ratio > 5:
                    warnings.append(
                        f"Class imbalance detected: majority/minority ratio = {ratio:.1f}x. "
                        "Consider SMOTE or class_weight='balanced'."
                    )

            if t.isnull().sum() > 0:
                warnings.append(
                    f"Target column has {int(t.isnull().sum())} missing values — "
                    "these rows will be dropped during training."
                )

    # ── Leakage hints ─────────────────────────────────────────────────────────
    if target_column and target_column in df.columns:
        for col in df.columns:
            if col == target_column:
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                try:
                    corr = abs(df[col].corr(df[target_column]))
                    if corr > 0.98:
                        warnings.append(
                            f"Possible leakage: '{col}' has {corr:.2f} correlation with target."
                        )
                except Exception:
                    pass

    return {
        "row_count":     n_rows,
        "column_count":  n_cols,
        "missing_cells": missing_cells,
        "missing_pct":   round(missing_cells / total_cells * 100, 2) if total_cells else 0,
        "columns":       columns,          # dict keyed by column name
        "target":        target_info,
        "warnings":      warnings,
        "imbalance_warning": warnings[0] if any("imbalance" in w for w in warnings) else None,
    }


def _safe(val):
    """Convert numpy scalar to Python native, handle nan/inf."""
    if val is None:
        return None
    if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
        return None
    if hasattr(val, "item"):
        return val.item()
    return val