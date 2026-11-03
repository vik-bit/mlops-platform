"""User-defined feature engineering for the training pipeline.

A training request can list transforms by column, for example:

    [{"op": "log",            "columns": ["income"]},
     {"op": "bin",            "columns": ["age"], "n_bins": 5},
     {"op": "datetime_parts", "columns": ["signup_date"], "parts": ["month", "dayofweek"]},
     {"op": "interaction",    "pairs": [["price", "quantity"]]},
     {"op": "target_encode",  "columns": ["city"]}]

Every transform becomes a branch of the pipeline's ColumnTransformer, so it is fitted only on the
rows it is trained on. Cross-validation therefore refits it on each training fold, and prediction
replays exactly what training did. This matters most for target_encode, which reads the label.

This module lives in shared/ because the fitted transformers are pickled into the saved model and
the deployment service must be able to import them to load it.
"""

from itertools import chain
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    FunctionTransformer, KBinsDiscretizer, OneHotEncoder, StandardScaler, TargetEncoder,
)

DATE_PARTS = ("year", "month", "day", "dayofweek", "hour")

# Transforms that replace the default handling of their columns, and the branch name each one gets
# in the ColumnTransformer. interaction adds features; its columns keep their default branch too.
REPLACING_OPS = {"log": "log", "bin": "bin", "datetime_parts": "date", "target_encode": "target_enc"}
OPS = (*REPLACING_OPS, "interaction")

# What kind of raw input each branch reads; the deployment service's schema endpoint uses this.
BRANCH_INPUT_KIND = {
    "num": "numeric", "log": "numeric", "bin": "numeric", "interaction": "numeric",
    "cat": "categorical", "target_enc": "categorical", "date": "datetime",
}


# ── Transformers ──────────────────────────────────────────────────────────────

def log1p_nonnegative(X):
    """log(1 + x), with values below 0 (only possible at prediction time) clipped to 0."""
    return np.log1p(np.clip(np.asarray(X, dtype=float), 0, None))


class DatetimeParts(BaseEstimator, TransformerMixin):
    """Split date/time columns into numeric parts (year, month, ...). Unparseable values become NaN."""

    def __init__(self, parts=DATE_PARTS):
        self.parts = parts

    def fit(self, X, y=None):
        self.feature_names_in_ = np.asarray(pd.DataFrame(X).columns, dtype=object)
        self.n_features_in_ = len(self.feature_names_in_)
        return self

    def transform(self, X):
        X = pd.DataFrame(X, columns=self.feature_names_in_)
        out = []
        for col in self.feature_names_in_:
            dt = pd.to_datetime(X[col], errors="coerce", format="mixed")
            out += [getattr(dt.dt, part).astype(float).to_numpy() for part in self.parts]
        return np.column_stack(out)

    def get_feature_names_out(self, input_features=None):
        return np.asarray([f"{c}_{p}" for c in self.feature_names_in_ for p in self.parts], dtype=object)


class Interactions(BaseEstimator, TransformerMixin):
    """Products of column pairs. Missing inputs are filled with the training median first."""

    def __init__(self, pairs=()):
        self.pairs = pairs

    def fit(self, X, y=None):
        X = pd.DataFrame(X)
        self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        self.n_features_in_ = len(self.feature_names_in_)
        self.medians_ = X.apply(pd.to_numeric, errors="coerce").median().fillna(0.0)
        return self

    def transform(self, X):
        X = pd.DataFrame(X, columns=self.feature_names_in_).apply(pd.to_numeric, errors="coerce")
        X = X.fillna(self.medians_)
        return np.column_stack([(X[a] * X[b]).to_numpy(dtype=float) for a, b in self.pairs])

    def get_feature_names_out(self, input_features=None):
        return np.asarray([f"{a}*{b}" for a, b in self.pairs], dtype=object)


# ── Validation ────────────────────────────────────────────────────────────────

def validate_transforms(X: pd.DataFrame, transforms: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Check a transform list against the training features; raise ValueError with a clear message."""
    transforms = [dict(t) for t in (transforms or [])]
    seen_ops, claimed = set(), {}
    numeric = set(X.select_dtypes(include="number").columns)

    for t in transforms:
        op = t.get("op")
        if op not in OPS:
            raise ValueError(f"Unknown transform '{op}'. Choose from: {', '.join(OPS)}")
        if op in seen_ops:
            raise ValueError(f"'{op}' is listed twice; put all its columns in one entry")
        seen_ops.add(op)

        if op == "interaction":
            pairs = [tuple(p) for p in t.get("pairs") or []]
            if not pairs or any(len(p) != 2 or p[0] == p[1] for p in pairs):
                raise ValueError("interaction needs 'pairs': a list of two different column names each")
            t["pairs"] = pairs
            columns = list(dict.fromkeys(chain.from_iterable(pairs)))
        else:
            columns = list(t.get("columns") or [])
            if not columns:
                raise ValueError(f"'{op}' needs at least one column")
        t["columns"] = columns

        missing = [c for c in columns if c not in X.columns]
        if missing:
            raise ValueError(f"'{op}': no such feature column(s): {', '.join(missing)}")

        if op in ("log", "bin", "interaction"):
            not_numeric = [c for c in columns if c not in numeric]
            if not_numeric:
                raise ValueError(f"'{op}' needs numeric columns: {', '.join(not_numeric)} are not")
        if op == "log":
            negative = [c for c in columns if (X[c].dropna() < 0).any()]
            if negative:
                raise ValueError(f"'log' needs values >= 0: {', '.join(negative)} has negatives")
        if op == "bin":
            n_bins = t.setdefault("n_bins", 5)
            if not isinstance(n_bins, int) or not 2 <= n_bins <= 100:
                raise ValueError("'bin' needs n_bins between 2 and 100")
        if op == "datetime_parts":
            parts = t.setdefault("parts", list(DATE_PARTS))
            bad = [p for p in parts if p not in DATE_PARTS]
            if not parts or bad:
                raise ValueError(f"'datetime_parts' parts must come from: {', '.join(DATE_PARTS)}")
            unparsed = [c for c in columns
                        if pd.to_datetime(X[c], errors="coerce", format="mixed").notna().sum() == 0]
            if unparsed:
                raise ValueError(f"'datetime_parts': no dates could be read in {', '.join(unparsed)}")

        if op in REPLACING_OPS:
            for c in columns:
                if c in claimed:
                    raise ValueError(f"Column '{c}' is used by both '{claimed[c]}' and '{op}'")
                claimed[c] = op
    return transforms


# ── Preprocessor ──────────────────────────────────────────────────────────────

def _scaled(*steps) -> Pipeline:
    return Pipeline([*steps, ("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])


def build_preprocessor(X: pd.DataFrame, transforms: Optional[List[Dict[str, Any]]] = None) -> ColumnTransformer:
    """Default handling per column type, plus the requested transforms as extra branches.

    Defaults: numeric columns are median-imputed and scaled; text, category and bool columns are
    imputed with the most frequent value and one-hot encoded.
    """
    transforms = validate_transforms(X, transforms)
    replaced = {c for t in transforms if t["op"] in REPLACING_OPS for c in t["columns"]}

    numeric = [c for c in X.select_dtypes(include="number").columns if c not in replaced]
    categorical = [c for c in X.select_dtypes(include=["object", "category", "bool", "string"]).columns
                   if c not in replaced]

    branches = [
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numeric),
        ("cat", Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), categorical),
    ]
    for t in transforms:
        op, columns = t["op"], t["columns"]
        if op == "log":
            branch = Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("log", FunctionTransformer(log1p_nonnegative, feature_names_out="one-to-one")),
                ("scale", StandardScaler()),
            ])
        elif op == "bin":
            branch = Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("bin", KBinsDiscretizer(n_bins=t["n_bins"], encode="onehot-dense", strategy="quantile",
                                         quantile_method="averaged_inverted_cdf")),
            ])
        elif op == "datetime_parts":
            branch = _scaled(("parts", DatetimeParts(parts=tuple(t["parts"]))))
        elif op == "interaction":
            branch = Pipeline([("product", Interactions(pairs=t["pairs"])), ("scale", StandardScaler())])
        else:  # target_encode
            # TargetEncoder cross-fits inside fit_transform, so even the training rows are encoded
            # with statistics from other rows; the seeded folds make that repeatable.
            folds = KFold(n_splits=5, shuffle=True, random_state=42)
            branch = Pipeline([("encode", TargetEncoder(cv=folds)), ("scale", StandardScaler())])
        name = "interaction" if op == "interaction" else REPLACING_OPS[op]
        branches.append((name, branch, columns))

    return ColumnTransformer(branches)
