from pydantic import BaseModel
from datetime import datetime


class DatasetResponse(BaseModel):

    id: int
    filename: str
    path: str
    created_at: datetime

    class Config:
        from_attributes = True