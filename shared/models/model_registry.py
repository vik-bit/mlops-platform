from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, LargeBinary, Text, func
from shared.database import Base


class ModelRegistry(Base):

    __tablename__ = "model_registry"

    id = Column(Integer, primary_key=True)

    training_job_id = Column(
        Integer,
        ForeignKey("training_jobs.id")
    )

    model_name = Column(String)

    model_version = Column(String)

    model_path = Column(String)       # kept for compatibility — no longer written to

    metadata_path = Column(String)    # kept for compatibility — no longer written to

    model_data = Column(LargeBinary, nullable=True)   # serialized pipeline bytes

    metadata_json = Column(Text, nullable=True)        # feature importance + distribution JSON

    stage = Column(String)

    accuracy = Column(String)

    created_at = Column(
        DateTime,
        server_default=func.now()
    )