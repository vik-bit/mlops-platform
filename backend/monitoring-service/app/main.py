from fastapi import FastAPI

from app.routes.monitoring import router as monitoring_router
from app.routes.logging import router as logging_router

app = FastAPI(
    title="Monitoring Service"
)

app.include_router(monitoring_router)
app.include_router(logging_router)