import os
import logging
import mlflow
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Read from environment instead of hardcoding the docker-compose service
# name. Render injects this via render.yaml's fromService/hostport — locally
# it falls back to the old compose hostname so nothing breaks in dev.
MLFLOW_URL = os.environ.get("MLFLOW_URL", "http://mlflow:5000")
MLFLOW_EXPERIMENT_NAME = "training-service"

_mlflow_initialized = False


def _ensure_mlflow_initialized() -> bool:
    """
    Lazily configure MLflow on first real use, instead of at import time.

    Running set_tracking_uri/set_experiment at module import meant any
    MLflow connectivity problem (wrong URL, MLflow still cold-starting,
    transient network blip) crashed the entire service before it could
    even start serving unrelated requests. Now a failure here just disables
    logging for this run and lets the rest of the app keep working.

    Returns True if MLflow is ready to use, False if it couldn't be reached.
    """
    global _mlflow_initialized
    if _mlflow_initialized:
        return True

    try:
        mlflow.set_tracking_uri(MLFLOW_URL)
        mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
        _mlflow_initialized = True
        return True
    except Exception as exc:
        logger.warning("MLflow unavailable at %s: %s — skipping run logging", MLFLOW_URL, exc)
        return False


def log_training(
    model_type: str,
    accuracy: float,
    hyperparameters: Optional[Dict[str, Any]] = None,
    extra_metrics: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Logs a training run to MLflow. Returns the run_id, or None if MLflow
    was unreachable — callers should treat a None return as "logging
    skipped" rather than a hard failure, since training itself still
    succeeded even if MLflow tracking didn't.
    """
    if not _ensure_mlflow_initialized():
        return None

    try:
        with mlflow.start_run() as run:
            mlflow.log_param("model_type", model_type)
            mlflow.log_metric("accuracy", accuracy)

            if hyperparameters:
                for key, value in hyperparameters.items():
                    mlflow.log_param(key, value)

            if extra_metrics:
                for key, value in extra_metrics.items():
                    if value is not None:
                        mlflow.log_metric(key, float(value))

            return run.info.run_id
    except Exception as exc:
        logger.warning("MLflow logging failed mid-run: %s", exc)
        return None