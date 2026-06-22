from sqlalchemy import Column, Integer, String, DateTime, LargeBinary
from datetime import datetime

from shared.database import Base


class Dataset(Base):

    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)

    filename = Column(String)

    path = Column(String)

    content = Column(LargeBinary, nullable=True)  # file bytes stored in Postgres

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )