import io
import joblib


def save_model(model, job_id: int) -> bytes:
    """
    Serialize the model pipeline to bytes in memory.
    The caller stores these bytes in the ModelRegistry.model_data column
    in Postgres instead of writing to local disk — survives service restarts.
    """
    buf = io.BytesIO()
    joblib.dump(model, buf)
    buf.seek(0)
    return buf.read()