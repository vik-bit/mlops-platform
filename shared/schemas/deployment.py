from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class DeployResponse(BaseModel):
    message: str
    endpoint: str


# ── Online prediction ─────────────────────────────────────────────────────────

class PredictionInput(BaseModel):
    """Positional features — legacy, kept for backward compat."""
    features: List[float]


class NamedPredictionInput(BaseModel):
    """Named features — preferred for production use."""
    features: Dict[str, Any]
    return_proba: bool = False


class PredictionResponse(BaseModel):
    prediction: Any
    probability: Optional[Dict[str, float]] = None
    latency_ms: Optional[float] = None


# ── Batch prediction ──────────────────────────────────────────────────────────

class BatchPredictionResponse(BaseModel):
    model_id: int
    total: int
    predictions: List[Any]
    latency_ms: float