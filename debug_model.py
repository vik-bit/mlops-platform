import joblib
import pandas as pd

pipeline = joblib.load("saved_models/model_1.pkl")

print("=" * 60)
print("PIPELINE")
print(pipeline)

print("\n" + "=" * 60)
print("MODEL TYPE")
print(type(pipeline.named_steps["model"]))

model = pipeline.named_steps["model"]

print("\n" + "=" * 60)
print("XGBOOST DETAILS")

if hasattr(model, "get_params"):
    print("n_estimators =", model.get_params().get("n_estimators"))
    print("max_depth =", model.get_params().get("max_depth"))
    print("learning_rate =", model.get_params().get("learning_rate"))

print("\n" + "=" * 60)
print("FEATURES EXPECTED")
print(pipeline.feature_names_in_)

sample = pd.DataFrame([{
    "longitude": -122.23,
    "latitude": 37.88,
    "housing_median_age": 41,
    "total_rooms": 880,
    "total_bedrooms": 129,
    "households": 126,
    "median_income": 8.3252,
    "median_house_value": 452600,
    "ocean_proximity": "NEAR BAY"
}])

print("\n" + "=" * 60)
print("INPUT")
print(sample)

print("\n" + "=" * 60)
print("TRANSFORMED SHAPE")

X_transformed = pipeline.named_steps["preprocessor"].transform(sample)
print(X_transformed.shape)

print("\n" + "=" * 60)
print("PREDICTION")

prediction = pipeline.predict(sample)
print(prediction)

if hasattr(model, "feature_importances_"):
    print("\n" + "=" * 60)
    print("TOP FEATURE IMPORTANCES")

    feature_names = pipeline.named_steps["preprocessor"].get_feature_names_out()

    pairs = sorted(
        zip(feature_names, model.feature_importances_),
        key=lambda x: x[1],
        reverse=True
    )

    for name, score in pairs[:15]:
        print(f"{name:<40} {score:.6f}")