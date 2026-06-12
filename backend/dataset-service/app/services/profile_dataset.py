import pandas as pd
import numpy as np

from typing import Optional


def profile_dataset(
    path: str,
    target_column: Optional[str] = None,
) -> dict:

    df = pd.read_csv(path)

    n_rows, n_cols = df.shape

    total_cells = n_rows * n_cols
    missing_cells = int(df.isnull().sum().sum())

    columns = {}

    for col in df.columns:

        series = df[col]

        dtype = str(series.dtype)

        n_missing = int(series.isnull().sum())

        n_unique = int(series.nunique())

        missing_pct = (
            round((n_missing / n_rows) * 100, 2)
            if n_rows
            else 0
        )

        col_info = {
            "dtype": dtype,
            "missing": n_missing,
            "missing_pct": missing_pct,
            "unique_count": n_unique,
        }

        if pd.api.types.is_numeric_dtype(series):

            col_info.update(
                {
                    "min": _safe(series.min()),
                    "max": _safe(series.max()),
                    "mean": _safe(series.mean()),
                    "std": _safe(series.std()),
                    "median": _safe(series.median()),
                    "skew": _safe(series.skew()),
                }
            )

        else:

            top = series.value_counts().head(5)

            col_info["top_values"] = [
                str(v)
                for v in top.index.tolist()
            ]

        columns[col] = col_info

    warnings = []

    target_info = None

    # =========================================================================
    # TARGET ANALYSIS
    # =========================================================================

    if target_column:

        if target_column not in df.columns:

            warnings.append(
                f"Target column '{target_column}' not found."
            )

        else:

            target = df[target_column]

            value_counts = target.value_counts()

            n_classes = int(target.nunique())

            is_numeric = pd.api.types.is_numeric_dtype(target)

            target_info = {
                "column": target_column,
                "dtype": str(target.dtype),
                "n_unique": n_classes,
                "missing": int(target.isnull().sum()),
                "missing_pct": round(
                    target.isnull().sum() / n_rows * 100,
                    2,
                ),
                "distribution": {
                    str(k): int(v)
                    for k, v in value_counts.items()
                },
                "suggested_task": (
                    "regression"
                    if is_numeric and n_classes > 20
                    else "classification"
                ),
            }

            if 2 <= n_classes <= 20:

                counts = value_counts.values

                ratio = (
                    counts.max() / counts.min()
                    if counts.min() > 0
                    else float("inf")
                )

                if ratio > 5:

                    warnings.append(
                        f"Class imbalance detected ({ratio:.1f}x)."
                    )

            if target.isnull().sum() > 0:

                warnings.append(
                    f"Target column contains "
                    f"{int(target.isnull().sum())} missing values."
                )

    # =========================================================================
    # NUMERIC DATAFRAME
    # =========================================================================

    numeric_df = df.select_dtypes(
        include=[np.number]
    )

    # =========================================================================
    # CORRELATION MATRIX
    # =========================================================================

    correlation_matrix = None

    if len(numeric_df.columns) > 1:

        try:

            correlation_matrix = (
                numeric_df.corr()
                .fillna(0)
                .round(4)
                .to_dict()
            )

        except Exception:

            correlation_matrix = None

    # =========================================================================
    # FEATURE RANKINGS
    # =========================================================================

    feature_rankings = []

    if (
        target_column
        and target_column in numeric_df.columns
    ):

        target_series = numeric_df[target_column]

        for col in numeric_df.columns:

            if col == target_column:
                continue

            try:

                corr = abs(
                    numeric_df[col].corr(
                        target_series
                    )
                )

                feature_rankings.append(
                    {
                        "feature": col,
                        "score": round(
                            float(corr),
                            4,
                        ),
                        "method": "correlation",
                    }
                )

            except Exception:
                pass

        feature_rankings.sort(
            key=lambda x: x["score"],
            reverse=True,
        )

    # =========================================================================
    # DATA LEAKAGE DETECTION
    # =========================================================================

    if (
        target_column
        and target_column in numeric_df.columns
    ):

        for col in numeric_df.columns:

            if col == target_column:
                continue

            try:

                corr = abs(
                    numeric_df[col].corr(
                        numeric_df[target_column]
                    )
                )

                if corr > 0.98:

                    warnings.append(
                        f"Possible leakage: "
                        f"'{col}' correlation={corr:.2f}"
                    )

            except Exception:
                pass

    # =========================================================================
    # OUTLIER DETECTION
    # =========================================================================

    outliers = {}

    for col in numeric_df.columns:

        try:

            q1 = numeric_df[col].quantile(0.25)
            q3 = numeric_df[col].quantile(0.75)

            iqr = q3 - q1

            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            count = int(
                (
                    (numeric_df[col] < lower)
                    | (numeric_df[col] > upper)
                ).sum()
            )

            outliers[col] = count

        except Exception:

            outliers[col] = 0

    # =========================================================================
    # DISTRIBUTION DATA
    # =========================================================================

    distributions = {}

    for col in numeric_df.columns[:20]:

        try:

            clean = numeric_df[col].dropna()

            counts, bins = np.histogram(
                clean,
                bins=20,
            )

            distributions[col] = {
                "bins": bins.tolist(),
                "counts": counts.tolist(),
            }

        except Exception:
            pass

    # =========================================================================
    # FEATURE ENGINEERING RECOMMENDATIONS
    # =========================================================================

    feature_engineering = []

    for col in df.columns:

        missing_ratio = df[col].isnull().mean()

        if missing_ratio > 0.20:

            feature_engineering.append(
                {
                    "feature": col,
                    "recommendation": "high_missing_values",
                    "action": "drop_or_impute",
                }
            )

    for col in df.select_dtypes(
        include=["object"]
    ).columns:

        unique = df[col].nunique()

        if unique > 50:

            feature_engineering.append(
                {
                    "feature": col,
                    "recommendation": "high_cardinality",
                    "action": "target_encoding",
                }
            )

    for col in numeric_df.columns:

        try:

            skew = numeric_df[col].skew()

            if abs(skew) > 1:

                feature_engineering.append(
                    {
                        "feature": col,
                        "recommendation": "skewed_distribution",
                        "action": "log_transform",
                    }
                )

        except Exception:
            pass

    for col in df.columns:

        try:

            top_freq = (
                df[col]
                .value_counts(normalize=True)
                .max()
            )

            if top_freq > 0.98:

                feature_engineering.append(
                    {
                        "feature": col,
                        "recommendation": "near_constant",
                        "action": "drop",
                    }
                )

        except Exception:
            pass

    # =========================================================================
    # TRAINING RECOMMENDATIONS
    # =========================================================================

    training_recommendations = {
        "suggested_model": None,
        "suggested_preprocessing": [],
    }

    if n_rows > 100000:

        training_recommendations[
            "suggested_model"
        ] = "lightgbm"

    elif n_rows > 10000:

        training_recommendations[
            "suggested_model"
        ] = "xgboost"

    else:

        training_recommendations[
            "suggested_model"
        ] = "random_forest"

    if missing_cells > 0:

        training_recommendations[
            "suggested_preprocessing"
        ].append(
            "median_imputation"
        )

    if any(
        "imbalance" in warning.lower()
        for warning in warnings
    ):

        training_recommendations[
            "suggested_preprocessing"
        ].append(
            "class_weight_balanced"
        )

    # =========================================================================
    # RESPONSE
    # =========================================================================

    return {
        "row_count": n_rows,
        "column_count": n_cols,
        "missing_cells": missing_cells,
        "missing_pct": (
            round(
                missing_cells
                / total_cells
                * 100,
                2,
            )
            if total_cells
            else 0
        ),
        "columns": columns,
        "target": target_info,
        "warnings": warnings,
        "imbalance_warning": next(
            (
                w
                for w in warnings
                if "imbalance" in w.lower()
            ),
            None,
        ),
        "correlation_matrix": correlation_matrix,
        "feature_rankings": feature_rankings[:20],
        "outliers": outliers,
        "distributions": distributions,
        "feature_engineering": feature_engineering,
        "training_recommendations": training_recommendations,
    }


def _safe(value):

    if value is None:
        return None

    if isinstance(value, float):

        if np.isnan(value):
            return None

        if np.isinf(value):
            return None

    if hasattr(value, "item"):

        try:
            return value.item()
        except Exception:
            pass

    return value