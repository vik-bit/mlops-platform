import os
import requests


MONITORING_URL = os.environ.get("MONITORING_URL", "http://monitoring-service:8000")


def log_prediction(
    model_id,
    input_data,
    prediction,
    latency_ms,
    status="success"
):
    try:
        requests.post(
            f"{MONITORING_URL}/log",
            json={
                "model_id": model_id,
                "input_data": str(input_data),
                "prediction": str(prediction),
                "latency_ms": latency_ms,
                "status": status
            },
            timeout=2
        )
    except Exception as e:
        print("Logging failed:", e)