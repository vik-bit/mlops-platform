from sqlalchemy import Column, Integer, Float, String, DateTime
from datetime import datetime

from shared.database import Base


class PredictionLog(Base):
    __tablename__ = "prediction_logs"

    id = Column(Integer, primary_key=True, index=True)

    model_id = Column(Integer, nullable=False)

    input_data = Column(String, nullable=False)

    prediction = Column(String, nullable=False)

    latency_ms = Column(Float, nullable=False)

    status = Column(String, default="success")

    created_at = Column(DateTime, default=datetime.utcnow)