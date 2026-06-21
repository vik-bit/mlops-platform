import os
import mlflow
from typing import Any, Dict, Optional

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MLFLOW_EXPERIMENT_NAME = os.environ.get("MLFLOW_EXPERIMENT_NAME", "training-service")

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)


def log_training(
    model_type: str,
    accuracy: float,
    hyperparameters: Optional[Dict[str, Any]] = None,
    extra_metrics: Optional[Dict[str, Any]] = None,
) -> str:
    with mlflow.start_run() as run:
        mlflow.log_param("model_type", model_type)

        if hyperparameters:
            for key, value in hyperparameters.items():
                mlflow.log_param(key, value)

        mlflow.log_metric("accuracy", accuracy)

        if extra_metrics:
            for key, value in extra_metrics.items():
                if value is not None:
                    mlflow.log_metric(key, float(value))

        return run.info.run_id