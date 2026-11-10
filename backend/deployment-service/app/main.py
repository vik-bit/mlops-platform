import os

from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from shared.database import Base, engine

# import ALL dependent models
from shared.models.training_job import TrainingJob
from shared.models.model_registry import ModelRegistry
from shared.models.deployment import Deployment
from shared.models.monitoring import PredictionLog
from shared.models import lifecycle  # noqa: F401  (rollouts, events, feedback, policy tables)

from app.routes.deployment import router
from app.routes.lifecycle import router as lifecycle_router
from app.services.rollouts import controller


Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(router)
app.include_router(lifecycle_router)


@app.on_event("startup")
def start_controller():
    if os.environ.get("ROLLOUT_CONTROLLER_ENABLED", "true").lower() == "true":
        controller.start()


# Render's health check hits GET /health on every deploy and on an ongoing
# basis afterward. Without this route every check 404s, Render assumes the
# service never came up, and the deploy times out after ~15 minutes even
# though the app itself started successfully (see "Application startup
# complete" / "Uvicorn running" in the logs — the process was fine the
# whole time, it just had nothing to answer the health probe with).
# Kubernetes uses it as the liveness probe: it must not depend on Postgres.
@app.get("/health")
def health():
    return {"status": "healthy", "service": "deployment-service"}


# Readiness probe: only take traffic while the database answers.
@app.get("/ready")
def ready(response: Response):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        response.status_code = 503
        return {"status": "not ready", "error": str(e)}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
