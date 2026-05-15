from fastapi import FastAPI
from app.routes.health import router as health_router

app = FastAPI(
    title="monitoring-service",
    version="1.0.0"
)

app.include_router(health_router)