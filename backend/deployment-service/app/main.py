from fastapi import FastAPI

from shared.database import Base, engine

# import ALL dependent models
from shared.models.training_job import TrainingJob
from shared.models.model_registry import ModelRegistry
from shared.models.deployment import Deployment

from app.routes.deployment import router


Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(router)


# Render's health check hits GET /health on every deploy and on an ongoing
# basis afterward. Without this route every check 404s, Render assumes the
# service never came up, and the deploy times out after ~15 minutes even
# though the app itself started successfully (see "Application startup
# complete" / "Uvicorn running" in the logs — the process was fine the
# whole time, it just had nothing to answer the health probe with).
@app.get("/health")
def health():
    return {"status": "healthy", "service": "deployment-service"}