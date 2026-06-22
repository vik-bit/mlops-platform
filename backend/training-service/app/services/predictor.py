import io
import joblib
import numpy as np

from shared.database import SessionLocal
from shared.models.model_registry import ModelRegistry


def load_model(model_id: int):
    """
    Load a model pipeline from the model_data bytes stored in Postgres.
    No local filesystem access — survives service restarts.
    """
    db = SessionLocal()
    try:
        entry = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not entry:
            raise Exception(f"Model {model_id} not found in registry")
        if not entry.model_data:
            raise Exception(f"Model {model_id} has no stored data — was it trained before the Postgres storage fix?")
        return joblib.load(io.BytesIO(entry.model_data))
    finally:
        db.close()


def predict(model_id: int, features):
    model = load_model(model_id)

    expected_features = model.n_features_in_

    if len(features) != expected_features:
        raise ValueError(
            f"Model expects {expected_features} features but received {len(features)}"
        )

    prediction = model.predict([features])
    return prediction[0]