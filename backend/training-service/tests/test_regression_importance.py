import numpy as np
import pandas as pd

from app.services.trainer import train_model


def test_regression_models_report_feature_importance():
    # Regression wraps the forest in TransformedTargetRegressor; importances used to come back None,
    # and with them the whole metadata (and so the drift baseline) was skipped.
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"a": rng.normal(size=200), "b": rng.normal(size=200)})
    df["y"] = 3 * df["a"] + rng.normal(scale=0.1, size=200)
    result = train_model(df, "y", model_type="random_forest", task_type="regression",
                         hyperparameters={"n_estimators": 10}, cv_folds=2)
    assert result.feature_importance
    assert max(result.feature_importance, key=result.feature_importance.get).endswith("a")
