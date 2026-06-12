from typing import Any, Dict, List, Optional
import json
import numpy as np
import pandas as pd

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

from sklearn.compose import TransformedTargetRegressor


def _get_transformed_feature_names(pipeline) -> List[str]:
    """Extract feature names from the fitted preprocessor."""
    try:
        return list(pipeline.named_steps["preprocessor"].get_feature_names_out())
    except Exception:
        # Fallback if get_feature_names_out fails
        try:
            model = pipeline.named_steps["model"]
            if hasattr(model, "regressor") and model.regressor is not None:
                n = model.regressor.n_features_in_
            else:
                n = model.n_features_in_
            return [f"feature_{i}" for i in range(n)]
        except Exception:
            return []


def _get_explainer(model_step, X_transformed):
    """Pick the best SHAP explainer for the model type, unwrapping meta-regressors."""
    # Unwrap TransformedTargetRegressor if present
    if isinstance(model_step, TransformedTargetRegressor):
        model_step = model_step.regressor_

    model_class = type(model_step).__name__

    tree_models = {
        "RandomForestClassifier", "RandomForestRegressor",
        "GradientBoostingClassifier", "GradientBoostingRegressor",
        "XGBClassifier", "XGBRegressor",
        "LGBMClassifier", "LGBMRegressor",
        "DecisionTreeClassifier", "DecisionTreeRegressor",
    }

    # Convert sparse matrices to dense arrays for TreeExplainer/LinearExplainer compatibility
    if hasattr(X_transformed, "toarray"):
        X_dense = X_transformed.toarray()
    else:
        X_dense = X_transformed

    if model_class in tree_models:
        return shap.TreeExplainer(model_step)

    # Linear models
    linear_models = {"LogisticRegression", "Ridge", "LinearRegression", "SVR"}
    if model_class in linear_models:
        return shap.LinearExplainer(model_step, X_dense)

    # Fallback: KernelExplainer (optimized background sample limit)
    background = shap.kmeans(X_dense, min(20, len(X_dense)))
    return shap.KernelExplainer(model_step.predict, background)


def compute_shap(
    pipeline,
    background_df: pd.DataFrame,
    explain_df: pd.DataFrame,
    max_display: int = 20,
) -> Dict[str, Any]:
    """
    Compute SHAP values seamlessly handling both classification and regression pipelines.
    """
    if not SHAP_AVAILABLE:
        return {"error": "SHAP not installed. Run: pip install shap"}

    try:
        preprocessor = pipeline.named_steps["preprocessor"]
        model_step   = pipeline.named_steps["model"]
        
        # Transform data to structural matrix format
        X_background = preprocessor.transform(background_df)
        X_explain    = preprocessor.transform(explain_df)
        
        # Ensure dense representations for processing stability
        if hasattr(X_explain, "toarray"):
            X_explain_dense = X_explain.toarray()
        else:
            X_explain_dense = np.array(X_explain)

        feature_names = _get_transformed_feature_names(pipeline)
        # Pad feature names fallback check
        if len(feature_names) < X_explain_dense.shape[1]:
            feature_names += [f"feature_{i}" for i in range(len(feature_names), X_explain_dense.shape[1])]

        explainer = _get_explainer(model_step, X_background)
        raw_shap  = explainer.shap_values(X_explain_dense)

        # ── Normalize modern SHAP Object API variation formats ────────────────
        if hasattr(raw_shap, "values"): # Handing shap.Explanation objects
            shap_arr = np.array(raw_shap.values)
        elif isinstance(raw_shap, list): # Multi-class lists fallback
            # Use positive class values if multi-class classification
            shap_arr = np.array(raw_shap[1]) if len(raw_shap) > 1 else np.array(raw_shap[0])
        else:
            shap_arr = np.array(raw_shap)

        # Handle multi-dimensional outputs (e.g., TreeExplainer multi-class arrays)
        if shap_arr.ndim == 3:
            shap_arr = shap_arr[:, :, 1] # Extract target classification class index

        if shap_arr.ndim == 1:
            shap_arr = shap_arr.reshape(1, -1)

        # ── Global importance calculation ─────────────────────────────────────
        mean_abs = np.abs(shap_arr).mean(axis=0)
        paired = sorted(
            zip(feature_names, mean_abs),
            key=lambda x: x[1], reverse=True
        )[:max_display]

        global_importance = {name: round(float(v), 6) for name, v in paired}

        # ── Local explanation (isolated single record baseline) ────────────────
        row_shap = shap_arr[0]
        row_data = X_explain_dense[0]

        local_explanation = sorted([
            {
                "feature":    name,
                "value":      _safe(val), # Fixed: cast occurs inside _safe now
                "shap_value": round(float(sv), 6),
                "direction":  "positive" if sv > 0 else "negative",
            }
            for name, val, sv in zip(feature_names, row_data, row_shap)
        ], key=lambda x: abs(x["shap_value"]), reverse=True)[:max_display]

        # ── Summary data slicing optimization for JSON Payloads ────────────────
        summary_data = []
        for name in global_importance.keys():
            if name in feature_names:
                idx = feature_names.index(name)
                summary_data.append({
                    "feature":       name,
                    "shap_values":  [round(float(v), 6) for v in shap_arr[:, idx]],
                    "feature_values": [_safe(v) for v in X_explain_dense[:100, idx]], # Fixed: cast inside _safe
                    "mean_abs_shap": round(float(mean_abs[idx]), 6),
                })

        # Base value normalizations
        base_val = explainer.expected_value
        if hasattr(base_val, "__len__") and not isinstance(base_val, (str, bytes)):
            base_val = base_val[1] if len(base_val) > 1 else base_val[0]

        return {
            "n_samples":         len(explain_df),
            "n_features":        len(feature_names),
            "global_importance": global_importance,
            "local_explanation": local_explanation,
            "summary_data":      summary_data,
            "base_value":        _safe(base_val), # Fixed: cast inside _safe
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


def _safe(val):
    """Safely converts numpy/python floats to JSON-compliant values."""
    if val is None:
        return None
    try:
        # Catch numpy types, infinity, and NaNs safely
        f_val = float(val)
        if np.isnan(f_val) or np.isinf(f_val):
            return None
        return f_val
    except (ValueError, TypeError):
        return None