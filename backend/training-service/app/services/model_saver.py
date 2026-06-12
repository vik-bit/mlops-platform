import joblib
import os


def save_model(model, job_id):

    os.makedirs("saved_models", exist_ok=True)

    path = f"saved_models/model_{job_id}.pkl"

    joblib.dump(model, path)

    return path