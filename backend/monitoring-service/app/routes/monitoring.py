import ast
import json
import os

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi.responses import PlainTextResponse

import requests
import psutil
import time

from prometheus_client import (
    Counter, Histogram, Gauge,
    generate_latest, CONTENT_TYPE_LATEST
)

from shared.database import SessionLocal
from shared.models.monitoring import PredictionLog

from app.services.drift import compute_drift

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Per-model stats ───────────────────────────────────────────────────────────

@router.get("/models/{model_id}/stats")
def get_model_stats(model_id: int, db: Session = Depends(get_db)):
    total       = db.query(PredictionLog).filter(PredictionLog.model_id == model_id).count()
    avg_latency = db.query(func.avg(PredictionLog.latency_ms)).filter(PredictionLog.model_id == model_id).scalar()
    successful  = db.query(PredictionLog).filter(PredictionLog.model_id == model_id, PredictionLog.status == "success").count()
    failed      = db.query(PredictionLog).filter(PredictionLog.model_id == model_id, PredictionLog.status == "failed").count()
    last        = db.query(PredictionLog).filter(PredictionLog.model_id == model_id).order_by(PredictionLog.created_at.desc()).first()

    success_rate = round((successful / total) * 100, 2) if total > 0 else 0

    return {
        "model_id":             model_id,
        "total_predictions":    total,
        "avg_latency_ms":       round(avg_latency or 0, 2),
        "successful_requests":  successful,
        "failed_requests":      failed,
        "success_rate":         success_rate,
        "last_prediction_time": last.created_at if last else None,
    }


# ── Prediction history ────────────────────────────────────────────────────────

@router.get("/models/{model_id}/history")
def get_prediction_history(
    model_id: int,
    limit: int = Query(default=50, le=500),
    db: Session = Depends(get_db),
):
    logs = (
        db.query(PredictionLog)
        .filter(PredictionLog.model_id == model_id)
        .order_by(PredictionLog.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id":         log.id,
            "model_id":   log.model_id,
            "prediction": log.prediction,
            "latency_ms": log.latency_ms,
            "status":     log.status,
            "created_at": log.created_at,
        }
        for log in logs
    ]


# ── Drift detection ───────────────────────────────────────────────────────────

@router.get("/models/{model_id}/drift")
def get_drift(
    model_id: int,
    window: int = Query(default=500, le=5000,
                        description="Number of recent predictions to analyse"),
    min_samples: int = Query(default=30,
                             description="Minimum samples per feature to run drift"),
    metadata_path: str = Query(...,
                               description="Path to the model _metadata.json file"),
    db: Session = Depends(get_db),
):
    """
    Drift detection for a deployed model.

    Reads the last `window` prediction logs, reconstructs input feature
    distributions from the stored input_data JSON, then compares against
    the training baseline in `_metadata.json`.

    Returns per-feature PSI + KS scores, overall drift signal,
    list of drifted features, and a retraining recommendation.
    """
    # Load training baseline from metadata
    try:
        with open(metadata_path) as f:
            meta = json.load(f)
    except FileNotFoundError:
        return {"error": f"Metadata not found at {metadata_path}"}
    except Exception as e:
        return {"error": f"Could not load metadata: {e}"}

    baseline = meta.get("training_distribution")
    if not baseline:
        return {
            "error": "No training_distribution in metadata. "
                     "Retrain the model to generate a baseline."
        }

    # Fetch recent prediction logs
    logs = (
        db.query(PredictionLog)
        .filter(PredictionLog.model_id == model_id)
        .order_by(PredictionLog.created_at.desc())
        .limit(window)
        .all()
    )

    if not logs:
        return {
            "model_id":      model_id,
            "status":        "no_predictions",
            "message":       "No prediction logs found for this model.",
            "overall_drift": "unknown",
        }

    # Parse input_data from each log into per-feature lists
    current_data: dict = {}
    parse_errors = 0

    for log in logs:
        try:
            # input_data is stored as a string repr of a dict
            raw = log.input_data
            if raw.startswith("{"):
                data = json.loads(raw)
            else:
                data = ast.literal_eval(raw)

            for feature, value in data.items():
                if feature not in current_data:
                    current_data[feature] = []
                try:
                    current_data[feature].append(float(value))
                except (TypeError, ValueError):
                    current_data[feature].append(value)

        except Exception:
            parse_errors += 1
            continue

    if not current_data:
        return {
            "model_id": model_id,
            "status":   "parse_error",
            "message":  f"Could not parse input_data from {len(logs)} logs ({parse_errors} errors).",
        }

    # Run drift computation
    drift_result = compute_drift(
        baseline=baseline,
        current_data=current_data,
        min_samples=min_samples,
    )

    return {
        "model_id":         model_id,
        "logs_analysed":    len(logs),
        "parse_errors":     parse_errors,
        "training_rows":    meta.get("training_rows"),
        "window":           window,
        **drift_result,
    }


# ── Prometheus metrics ────────────────────────────────────────────────────────

REQUEST_COUNT   = Counter("monitoring_requests_total",   "Total monitoring requests")
REQUEST_LATENCY = Histogram("service_latency_seconds",   "Latency of services")
CPU_USAGE       = Gauge("system_cpu_usage_percent",      "CPU usage percent")
MEMORY_USAGE    = Gauge("system_memory_usage_percent",   "Memory usage percent")
DISK_USAGE      = Gauge("system_disk_usage_percent",     "Disk usage percent")

# FIX: every URL here was hardcoded to a Docker Compose hostname
# (e.g. "http://dataset-service:8000/docs"). On Render those hostnames don't
# resolve, so every requests.get() below threw a ConnectionError, which the
# except block silently turned into {"status": "offline", "error": ...} —
# meaning every single service has been showing as "offline" in the System
# Health panel even though all 5 are actually running fine. This was a
# *silent* failure (caught exception, no 500, no log noise) which is why it
# didn't show up in any of the error reports so far this session — the
# dashboard just quietly lied about service health.
#
# Each *_SERVICE_URL env var is set in render.yaml to the real
# https://mlops-<service>.onrender.com URL. /docs is appended the same way
# as before so this still hits each service's FastAPI docs page as a
# lightweight liveness probe (could be swapped for /health if preferred —
# /docs works fine here since we only care about getting any 200 back).
SERVICES = {
    "dataset-service":    f"{os.environ.get('DATASET_SERVICE_URL',   'http://dataset-service:8000')}/docs",
    "training-service":   f"{os.environ.get('TRAINING_SERVICE_URL',  'http://training-service:8000')}/docs",
    "deployment-service": f"{os.environ.get('DEPLOYMENT_SERVICE_URL','http://deployment-service:8000')}/docs",
    "monitoring-service": f"{os.environ.get('MONITORING_SERVICE_URL','http://monitoring-service:8000')}/docs",
    "mlflow":             os.environ.get('MLFLOW_URL', 'http://mlflow:5000'),
}


@router.get("/health")
def health():
    return {"status": "healthy", "service": "monitoring-service"}


@router.get("/system-overview")
def system_overview():
    REQUEST_COUNT.inc()

    services_status = {}
    for name, url in SERVICES.items():
        try:
            start = time.time()
            r = requests.get(url, timeout=2)
            latency = round((time.time() - start) * 1000, 2)
            REQUEST_LATENCY.observe(latency / 1000)
            services_status[name] = {
                "status":      "online",
                "status_code": r.status_code,
                "latency_ms":  latency,
            }
        except Exception as e:
            services_status[name] = {"status": "offline", "error": str(e)}

    cpu    = psutil.cpu_percent()
    memory = psutil.virtual_memory().percent
    disk   = psutil.disk_usage("/").percent
    CPU_USAGE.set(cpu)
    MEMORY_USAGE.set(memory)
    DISK_USAGE.set(disk)

    return {
        "platform_status": "running",
        "services":        services_status,
        "system_metrics":  {
            "cpu_percent":    cpu,
            "memory_percent": memory,
            "disk_percent":   disk,
        },
    }


@router.get("/metrics")
def metrics():
    return PlainTextResponse(
        generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )