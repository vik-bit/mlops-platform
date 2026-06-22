import os
import requests


MONITORING_URL = os.environ.get(
    "MONITORING_SERVICE_URL",
    "http://monitoring-service:8000"
)


def log_prediction(
    model_id,
    input_data,
    prediction,
    latency_ms,
    status="success"
):
    try:
        response = requests.post(
            f"{MONITORING_URL}/log",
            json={
                "model_id": model_id,
                "input_data": str(input_data),
                "prediction": str(prediction),
                "latency_ms": latency_ms,
                "status": status
            },
            timeout=30
        )

        print(
            "Prediction log:",
            response.status_code,
            response.text
        )

    except Exception as e:
        print(
            "Logging failed:",
            repr(e)
        )