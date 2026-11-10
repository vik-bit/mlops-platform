"""Prometheus metrics for the deployment service (scraped at GET /metrics)."""

from prometheus_client import Counter, Histogram

PREDICTIONS = Counter(
    "deployment_predictions_total", "Predictions scored", ["model_id", "arm", "status"]
)
INFERENCE_LATENCY = Histogram(
    "deployment_inference_latency_seconds", "Model inference latency", ["arm"],
    buckets=(0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
)
SHADOW_SKIPPED = Counter(
    "deployment_shadow_skipped_total", "Shadow scorings skipped because the shadow queue was full"
)


def observe(model_id: int, arm: str, status: str, latency_ms: float):
    PREDICTIONS.labels(str(model_id), arm, status).inc()
    INFERENCE_LATENCY.labels(arm).observe(latency_ms / 1000.0)
