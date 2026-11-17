import os

from fastapi import Depends, FastAPI, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.database import Base, SessionLocal, engine
from shared.models.deployment import Deployment
from shared.models.monitoring import PredictionLog  # noqa: F401
from shared.models import lifecycle  # noqa: F401  (lifecycle tables)

from app.routes.monitoring import router as monitoring_router
from app.routes.logging import router as logging_router
from app.services.lifecycle import check_deployment, controller

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Monitoring Service"
)

app.include_router(monitoring_router)
app.include_router(logging_router)


@app.on_event("startup")
def start_retrain_controller():
    if os.environ.get("RETRAIN_CONTROLLER_ENABLED", "true").lower() == "true":
        controller.start()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/deployments/{deployment_id}/lifecycle-check")
def lifecycle_check(deployment_id: int, queue: bool = False, db: Session = Depends(get_db)):
    """Run the drift -> retrain decision once. With queue=false (default) nothing is queued."""
    dep = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not dep:
        raise HTTPException(404, "Deployment not found")
    return check_deployment(db, dep, queue=queue)


@app.get("/lifecycle/status")
def lifecycle_status():
    return {"interval_s": controller.interval_s, "last_run": controller.last_run,
            "last_error": controller.last_error, "last_results": controller.last_results}


@app.get("/ready")
def ready(response: Response):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        response.status_code = 503
        return {"status": "not ready", "error": str(e)}
