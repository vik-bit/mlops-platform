from pydantic import BaseModel
from typing import List, Any


class PredictionRequest(BaseModel):

    model_id: int

    features: List[Any]


class PredictionResponse(BaseModel):

    prediction: Any