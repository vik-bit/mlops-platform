from fastapi import FastAPI

from shared.database import Base, engine

from shared.models.training_job import TrainingJob

from app.routes.training import router
from shared.models.dataset import Dataset
from shared.models.model_registry import ModelRegistry



Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Training Service"
)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}