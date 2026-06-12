from pydantic import BaseModel
from typing import Optional, Dict, Any, Literal
from datetime import datetime


class TrainingRequest(BaseModel):
    dataset_id:      int
    target_column:   str
    model_type:      str
    task_type:       Literal["classification", "regression"] = "classification"
    hyperparameters: Optional[Dict[str, Any]] = None


class TrainingResponse(BaseModel):
    id:             int
    dataset_id:     int
    model_type:     str
    task_type:      Optional[str]  = None
    target_column:  Optional[str]  = None
    status:         str

    # Core score
    accuracy:       Optional[str]   = None

    # Classification metrics
    precision:      Optional[float] = None
    recall:         Optional[float] = None
    f1_score:       Optional[float] = None
    roc_auc:        Optional[float] = None

    # Regression metrics
    r2_score:       Optional[float] = None
    mae:            Optional[float] = None
    rmse:           Optional[float] = None

    # Cross-validation
    cv_mean:        Optional[float] = None
    cv_std:         Optional[float] = None

    hyperparameters: Optional[Dict[str, Any]] = None
    mlflow_run_id:   Optional[str]  = None
    error_message:   Optional[str]  = None
    created_at:      datetime

    class Config:
        from_attributes = True