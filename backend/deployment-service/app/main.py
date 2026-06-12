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