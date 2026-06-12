from sqlalchemy import Column, Integer, String
from shared.database import Base


class Deployment(Base):

    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True, index=True)

    model_id = Column(Integer)

    status = Column(String)

    endpoint = Column(String)