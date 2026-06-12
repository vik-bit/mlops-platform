import joblib
import os
import numpy as np


def load_model(model_id: int):

    model_path = f"saved_models/model_{model_id}.pkl"

    if not os.path.exists(model_path):
        raise Exception("Model not found")

    model = joblib.load(model_path)

    return model


def predict(model_id, features):

    model = load_model(model_id)

    expected_features = model.n_features_in_

    if len(features) != expected_features:

        raise ValueError(
            f"Model expects {expected_features} features but received {len(features)}"
        )

    prediction = model.predict([features])

    return prediction[0]