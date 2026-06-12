from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    Float
)
from sqlalchemy.sql import func

from shared.database import Base


class TrainingJob(Base):

    __tablename__ = "training_jobs"

    id = Column(Integer, primary_key=True, index=True)

    dataset_id = Column(Integer)

    model_type = Column(String, nullable=False)

    task_type = Column(String, nullable=False)

    target_column = Column(String, nullable=False)

    status = Column(String, default="queued")

    accuracy = Column(Float)

    precision = Column(Float)

    recall = Column(Float)

    f1_score = Column(Float)

    r2_score = Column(Float)

    mae = Column(Float)

    rmse = Column(Float)

    cv_mean = Column(Float)

    cv_std = Column(Float)

    hyperparameters = Column(Text)

    mlflow_run_id = Column(String)

    error_message = Column(Text)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )