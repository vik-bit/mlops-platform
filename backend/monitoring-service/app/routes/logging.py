from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from shared.database import SessionLocal
from shared.models.monitoring import PredictionLog

router = APIRouter()


class PredictionLogRequest(BaseModel):
    model_id: int
    input_data: str
    prediction: str
    latency_ms: float
    status: str = "success"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/log")
def log_prediction(
    request: PredictionLogRequest,
    db: Session = Depends(get_db)
):

    log = PredictionLog(
        model_id=request.model_id,
        input_data=request.input_data,
        prediction=request.prediction,
        latency_ms=request.latency_ms,
        status=request.status
    )

    db.add(log)
    db.commit()

    return {
        "message": "Prediction logged"
    }

class PredictionLogBatch(BaseModel):
    logs: list[PredictionLogRequest]


@router.post("/log/batch")
def log_predictions_batch(request: PredictionLogBatch, db: Session = Depends(get_db)):
    """Bulk insert; the deployment service flushes its log queue here every ~0.5 s."""
    db.bulk_save_objects([
        PredictionLog(model_id=l.model_id, input_data=l.input_data, prediction=l.prediction,
                      latency_ms=l.latency_ms, status=l.status)
        for l in request.logs
    ])
    db.commit()
    return {"message": "Prediction logs stored", "count": len(request.logs)}
