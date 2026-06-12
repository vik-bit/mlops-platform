from typing import Any, Dict, Optional, Tuple
import json

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import train_test_split, cross_validate, StratifiedKFold, KFold
from sklearn.metrics import (
    accuracy_score, r2_score,
    precision_score, recall_score, f1_score,
    roc_auc_score, mean_absolute_error, mean_squared_error,
)

from sklearn.ensemble import (
    RandomForestClassifier, RandomForestRegressor,
    GradientBoostingClassifier, GradientBoostingRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.svm import SVC, SVR
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

try:
    from xgboost import XGBClassifier, XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    from lightgbm import LGBMClassifier, LGBMRegressor
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
from sklearn.compose import TransformedTargetRegressor

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULTS: Dict[str, Dict[str, Any]] = {
    "random_forest":       {"n_estimators": 100, "random_state": 42},
    "gradient_boosting":   {"n_estimators": 100, "learning_rate": 0.1, "random_state": 42},
    "logistic_regression": {"max_iter": 1000, "random_state": 42},
    "svm":                 {"C": 1.0, "kernel": "rbf", "probability": True},
    "knn":                 {"n_neighbors": 5},
    "decision_tree":       {"random_state": 42},
    "xgboost":             {"n_estimators": 100, "learning_rate": 0.1, "random_state": 42, "eval_metric": "logloss"},
    "lightgbm":            {"n_estimators": 100, "learning_rate": 0.1, "random_state": 42, "verbose": -1},
}


# ── Model builders ────────────────────────────────────────────────────────────

def build_classifier(model_type: str, params: Dict[str, Any]):
    if model_type == "random_forest":       return RandomForestClassifier(**params)
    if model_type == "gradient_boosting":   return GradientBoostingClassifier(**params)
    if model_type == "logistic_regression": return LogisticRegression(**params)
    if model_type == "svm":                 return SVC(**params)
    if model_type == "knn":                 return KNeighborsClassifier(**params)
    if model_type == "decision_tree":       return DecisionTreeClassifier(**params)
    if model_type == "xgboost":
        if not XGBOOST_AVAILABLE: raise ValueError("XGBoost not installed")
        params.pop("use_label_encoder", None)
        return XGBClassifier(**params)
    if model_type == "lightgbm":
        if not LIGHTGBM_AVAILABLE: raise ValueError("LightGBM not installed")
        return LGBMClassifier(**params)
    raise ValueError(f"Unknown model type: {model_type}")


def build_regressor(model_type: str, params: Dict[str, Any]):
    params = {k: v for k, v in params.items() if k not in {"probability", "eval_metric", "use_label_encoder"}}

    # 1. Build the base estimator for all supported types
    if model_type == "random_forest":
        base_estimator = RandomForestRegressor(**params)
    elif model_type == "gradient_boosting":
        base_estimator = GradientBoostingRegressor(**params)
    elif model_type == "logistic_regression" or model_type == "ridge":
        # Overriding logistic_regression fallback to Ridge for regression tasks
        base_estimator = Ridge(**params)
    elif model_type == "svm":
        # SVM for regression is SVR (probability parameter is not valid here)
        params.pop("probability", None)
        base_estimator = SVR(**params)
    elif model_type == "knn":
        base_estimator = KNeighborsRegressor(**params)
    elif model_type == "decision_tree":
        base_estimator = DecisionTreeRegressor(**params)
    elif model_type == "xgboost":
        if not XGBOOST_AVAILABLE: 
            raise ValueError("XGBoost not installed")
        base_estimator = XGBRegressor(**params)
    elif model_type == "lightgbm":
        if not LIGHTGBM_AVAILABLE: 
            raise ValueError("LightGBM not installed")
        base_estimator = LGBMRegressor(**params)
    else:
        raise ValueError(f"Unknown regression model type: {model_type}")

    # 2. Wrap it so it automatically scales 'y' on fit() and inverse-scales on predict()
    return TransformedTargetRegressor(
        regressor=base_estimator,
        transformer=StandardScaler() # or a custom mean-centering transformer
    )


# ── Preprocessor ──────────────────────────────────────────────────────────────

def build_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    numeric_features     = X.select_dtypes(include=["int64","float64","int32","float32"]).columns.tolist()
    categorical_features = X.select_dtypes(include=["object","category","bool"]).columns.tolist()

    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  StandardScaler()),
    ])
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    return ColumnTransformer(transformers=[
        ("num", numeric_pipeline,     numeric_features),
        ("cat", categorical_pipeline, categorical_features),
    ])


# ── Feature importance ────────────────────────────────────────────────────────

def extract_feature_importance(pipeline: Pipeline, feature_names: list) -> Optional[Dict[str, float]]:
    """
    Extract feature importances from the trained model step.
    Works for tree-based models and linear models.
    Returns top-20 as {feature_name: importance} sorted descending.
    """
    try:
        model = pipeline.named_steps["model"]
        preprocessor = pipeline.named_steps["preprocessor"]

        # Get transformed feature names
        try:
            transformed_names = preprocessor.get_feature_names_out()
        except Exception:
            transformed_names = [f"feature_{i}" for i in range(pipeline.n_features_in_)]

        importances = None

        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
        elif hasattr(model, "coef_"):
            coef = model.coef_
            importances = np.abs(coef).mean(axis=0) if coef.ndim > 1 else np.abs(coef)

        if importances is None:
            return None

        paired = sorted(
            zip(transformed_names, importances),
            key=lambda x: x[1], reverse=True
        )[:20]

        return {name: round(float(imp), 6) for name, imp in paired}

    except Exception:
        return None


# ── Training result type ──────────────────────────────────────────────────────

class TrainingResult:
    def __init__(self):
        self.pipeline:           Any             = None
        self.accuracy:           Optional[float] = None   # classification
        self.precision:          Optional[float] = None
        self.recall:             Optional[float] = None
        self.f1:                 Optional[float] = None
        self.roc_auc:            Optional[float] = None
        self.r2:                 Optional[float] = None   # regression
        self.mae:                Optional[float] = None
        self.rmse:               Optional[float] = None
        self.cv_mean:            Optional[float] = None
        self.cv_std:             Optional[float] = None
        self.feature_importance: Optional[Dict]  = None


# ── Main training function ────────────────────────────────────────────────────

def train_model(
    df: pd.DataFrame,
    target_column: str,
    model_type: str = "random_forest",
    task_type: str = "classification",
    hyperparameters: Optional[Dict[str, Any]] = None,
    cv_folds: int = 5,
) -> TrainingResult:
    """
    Train with preprocessing pipeline, cross-validation, and full metrics.
    Returns a TrainingResult with all metric fields populated.
    """
    result = TrainingResult()

    # ── Prep ─────────────────────────────────────────────────────────────────
    df = df.dropna(subset=[target_column])
    X  = df.drop(columns=[target_column, "id"], errors="ignore")
    y  = df[target_column]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42,
        stratify=y if task_type == "classification" and y.nunique() <= 20 else None
    )

    params = {**DEFAULTS.get(model_type, {}), **(hyperparameters or {})}

    # ── Build pipeline ───────────────────────────────────────────────────────
    preprocessor = build_preprocessor(X)

    if task_type == "regression":
        estimator = build_regressor(model_type, dict(params))
        cv_scoring = "r2"
        cv = KFold(n_splits=cv_folds, shuffle=True, random_state=42)
    else:
        estimator = build_classifier(model_type, dict(params))
        cv_scoring = "accuracy"
        n_classes  = y.nunique()
        cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42) if n_classes <= 20 else KFold(n_splits=cv_folds, shuffle=True, random_state=42)

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("model",        estimator),
    ])

    # ── Cross-validation ─────────────────────────────────────────────────────
    try:
        cv_results = cross_validate(pipeline, X, y, cv=cv, scoring=cv_scoring, n_jobs=-1)
        result.cv_mean = float(round(cv_results["test_score"].mean(), 4))
        result.cv_std  = float(round(cv_results["test_score"].std(),  4))
    except Exception as e:
        print(f"Cross-validation failed (non-fatal): {e}")

    # ── Final fit on train split ──────────────────────────────────────────────
    pipeline.fit(X_train, y_train)
    predictions = pipeline.predict(X_test)

    # ── Metrics ───────────────────────────────────────────────────────────────
    if task_type == "regression":
        result.r2   = float(round(r2_score(y_test, predictions), 4))
        result.mae  = float(round(mean_absolute_error(y_test, predictions), 4))
        result.rmse = float(round(np.sqrt(mean_squared_error(y_test, predictions)), 4))
        result.accuracy = result.r2   # store r2 in accuracy col for compat

    else:
        avg = "binary" if y.nunique() == 2 else "weighted"
        result.accuracy  = float(round(accuracy_score(y_test, predictions), 4))
        result.precision = float(round(precision_score(y_test, predictions, average=avg, zero_division=0), 4))
        result.recall    = float(round(recall_score(y_test, predictions, average=avg, zero_division=0), 4))
        result.f1        = float(round(f1_score(y_test, predictions, average=avg, zero_division=0), 4))

        # ROC-AUC — needs predict_proba, binary only
        try:
            model_step = pipeline.named_steps["model"]
            if hasattr(model_step, "predict_proba") and y.nunique() == 2:
                proba = pipeline.predict_proba(X_test)[:, 1]
                result.roc_auc = float(round(roc_auc_score(y_test, proba), 4))
        except Exception:
            pass

    # ── Feature importance ────────────────────────────────────────────────────
    result.feature_importance = extract_feature_importance(pipeline, X.columns.tolist())

    result.pipeline = pipeline
    return result