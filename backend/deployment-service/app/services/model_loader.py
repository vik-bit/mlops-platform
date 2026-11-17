import io
import os
from functools import lru_cache

import joblib
from shared.database import SessionLocal
from shared.models.model_registry import ModelRegistry

# A registry entry's bytes never change after training, so a loaded pipeline can be reused.
# v1 unpickled the model from Postgres on every request.
MODEL_CACHE_SIZE = int(os.environ.get("MODEL_CACHE_SIZE", "16"))


def _load_from_db(model_id: int):
    db = SessionLocal()
    try:
        entry = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not entry:
            raise Exception(f"Model {model_id} not found in registry")
        if not entry.model_data:
            raise Exception(f"Model {model_id} has no stored data — retrain to generate a persistent model")
        return joblib.load(io.BytesIO(entry.model_data))
    finally:
        db.close()


@lru_cache(maxsize=MODEL_CACHE_SIZE)
def load_model(model_id: int):
    """
    Load a model pipeline from the model_data bytes stored in Postgres (cached per process).
    model_id is the ModelRegistry.id — not a file path. Failures are not cached.
    """
    return _load_from_db(model_id)
