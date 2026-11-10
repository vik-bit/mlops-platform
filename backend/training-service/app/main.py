from fastapi import FastAPI, Response
from sqlalchemy import text

from shared.database import Base, engine

from shared.models.training_job import TrainingJob

from app.routes.training import router
from shared.models.dataset import Dataset
from shared.models.model_registry import ModelRegistry
from shared.models import lifecycle  # noqa: F401  (labelled_samples, lifecycle_events, policies)



Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Training Service"
)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready(response: Response):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        response.status_code = 503
        return {"status": "not ready", "error": str(e)}