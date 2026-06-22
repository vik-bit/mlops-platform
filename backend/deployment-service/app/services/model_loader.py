import io
import joblib
from shared.database import SessionLocal
from shared.models.model_registry import ModelRegistry


def load_model(model_id: int):
    """
    Load a model pipeline from the model_data bytes stored in Postgres.
    model_id is the ModelRegistry.id — not a file path.
    """
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