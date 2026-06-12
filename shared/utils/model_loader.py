import joblib


def load_model(model_path):

    model = joblib.load(model_path)

    return model