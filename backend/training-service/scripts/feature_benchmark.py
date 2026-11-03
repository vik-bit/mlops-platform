"""Does feature engineering help? A before/after measurement on the Adult census income data.

Run from backend/training-service with the repo root on PYTHONPATH:
    PYTHONPATH=.:../.. python scripts/feature_benchmark.py

Downloads Adult (OpenML 1590, 48,842 rows) on first use. The transform set below was fixed before
the first run, from the usual reasons (skewed money columns, non-linear age, many-level
categories); it was not tuned on these scores. Both pipelines use the same 5 folds, so the
per-fold difference is paired.
"""

import time

import numpy as np
from sklearn.datasets import fetch_openml
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

from app.services.trainer import DEFAULTS, build_classifier
from shared.ml.features import build_preprocessor

TRANSFORMS = [
    {"op": "log", "columns": ["capital-gain", "capital-loss"]},
    {"op": "bin", "columns": ["age", "hours-per-week"], "n_bins": 8},
    {"op": "target_encode", "columns": ["native-country", "occupation"]},
    {"op": "interaction", "pairs": [["education-num", "hours-per-week"]]},
]
MODELS = ("logistic_regression", "random_forest")


def main():
    data = fetch_openml(data_id=1590, as_frame=True)
    X = data.data.copy()
    for col in X.select_dtypes("category").columns:  # same dtypes as a CSV upload
        X[col] = X[col].astype(object)
    y = (data.target == ">50K").astype(int)
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    print(f"Adult: {len(X):,} rows, {X.shape[1]} features, {y.mean():.1%} positive\n")
    print("| Model | Default preprocessing | With feature transforms | Paired difference (min to max over folds) |")
    print("|---|---|---|---|")
    for model in MODELS:
        scores, seconds = {}, {}
        for name, transforms in (("default", None), ("engineered", TRANSFORMS)):
            pipe = Pipeline([("preprocessor", build_preprocessor(X, transforms)),
                             ("model", build_classifier(model, dict(DEFAULTS[model])))])
            started = time.perf_counter()
            scores[name] = cross_val_score(pipe, X, y, cv=folds, scoring="accuracy", n_jobs=-1)
            seconds[name] = time.perf_counter() - started
        diff = scores["engineered"] - scores["default"]
        print(f"| {model} | {scores['default'].mean():.2%} ± {scores['default'].std():.2%} "
              f"| {scores['engineered'].mean():.2%} ± {scores['engineered'].std():.2%} "
              f"| {diff.mean() * 100:+.2f} pts ({diff.min() * 100:+.2f} to {diff.max() * 100:+.2f}) |")
        print(f"<!-- {model}: {seconds['default']:.0f} s vs {seconds['engineered']:.0f} s; "
              f"folds {np.round(scores['default'], 4).tolist()} vs {np.round(scores['engineered'], 4).tolist()} -->")


if __name__ == "__main__":
    main()
