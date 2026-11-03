import io
import subprocess
import sys

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import TargetEncoder

from app.services.trainer import train_model
from conftest import REPO_ROOT
from shared.ml.features import BRANCH_INPUT_KIND, build_preprocessor, validate_transforms

ALL_TRANSFORMS = [
    {"op": "log", "columns": ["income"]},
    {"op": "bin", "columns": ["age"], "n_bins": 4},
    {"op": "datetime_parts", "columns": ["signup"], "parts": ["month", "dayofweek", "hour"]},
    {"op": "interaction", "pairs": [["price", "qty"]]},
    {"op": "target_encode", "columns": ["city"]},
]


@pytest.fixture
def df():
    rng = np.random.default_rng(0)
    n = 300
    frame = pd.DataFrame({
        "income": rng.lognormal(10, 1, n),
        "age": rng.integers(18, 80, n).astype(float),
        "signup": pd.date_range("2024-01-01", periods=n, freq="7h").astype(str),
        "price": rng.uniform(1, 10, n),
        "qty": rng.integers(1, 5, n),
        "city": rng.choice(list("abcdefgh"), n),
    })
    frame.loc[::17, "income"] = np.nan
    frame.loc[::23, "signup"] = "not a date"
    frame["y"] = (frame.price * frame.qty + rng.normal(0, 2, n) > 15).astype(int)
    return frame


def features(frame):
    return frame.drop(columns=["y"])


# ── What each transform produces ──────────────────────────────────────────────

def test_no_transforms_keeps_the_default_branches(df):
    pre = build_preprocessor(features(df)).fit(features(df))
    names = list(pre.get_feature_names_out())
    assert "num__income" in names and "num__price" in names
    assert "cat__city_a" in names and "cat__signup_2024-01-01 07:00:00" in names


def test_each_transform_gets_its_own_branch_and_replaces_the_default(df):
    X = features(df)
    pre = build_preprocessor(X, ALL_TRANSFORMS).fit(X, df["y"])
    names = list(pre.get_feature_names_out())

    assert names == [
        "num__price", "num__qty",
        "log__income",
        "bin__age_0.0", "bin__age_1.0", "bin__age_2.0", "bin__age_3.0",
        "date__signup_month", "date__signup_dayofweek", "date__signup_hour",
        "interaction__price*qty",
        "target_enc__city",
    ]
    out = pre.transform(X)
    assert out.shape == (len(X), len(names))
    assert not np.isnan(out).any()  # missing incomes and unreadable dates were imputed
    # quantile bins: every row lands in exactly one bin
    bins = out[:, 3:7]
    assert (bins.sum(axis=1) == 1).all()


def test_values_match_hand_computation(df):
    X = features(df)
    pre = build_preprocessor(X, ALL_TRANSFORMS).fit(X, df["y"])
    branches = dict((name, est) for name, est, _ in pre.transformers_)

    row = X.iloc[[1]]  # 2024-01-01 07:00, a Monday
    log = branches["log"]
    assert log[:-1].transform(row[["income"]])[0, 0] == pytest.approx(np.log1p(row.income.iloc[0]))
    parts = branches["date"].named_steps["parts"].transform(row[["signup"]])
    assert parts.tolist() == [[1.0, 0.0, 7.0]]
    product = branches["interaction"].named_steps["product"].transform(row[["price", "qty"]])
    assert product[0, 0] == pytest.approx(row.price.iloc[0] * row.qty.iloc[0])


def test_unseen_and_bad_values_at_prediction_time_do_not_crash(df):
    result = train_model(df, "y", model_type="logistic_regression", feature_transforms=ALL_TRANSFORMS)
    odd = pd.DataFrame([{"income": -5.0, "age": 200.0, "signup": "garbage", "price": np.nan,
                         "qty": 2, "city": "never-seen"}])
    assert result.pipeline.predict(odd)[0] in (0, 1)


# ── Training ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("model_type", ["logistic_regression", "random_forest"])
def test_training_with_transforms_cross_validates(df, model_type):
    result = train_model(df, "y", model_type=model_type, feature_transforms=ALL_TRANSFORMS)
    # cross-validation failures are caught and logged in train_model, so check it really ran
    assert result.cv_mean is not None and result.cv_mean > 0.8
    assert result.feature_transforms[1]["n_bins"] == 4
    assert result.feature_transforms[3]["pairs"] == [("price", "qty")]


def test_regression_target_encoding_uses_the_raw_target(df):
    reg = df.assign(y=df.price * df.qty + df.city.map({c: i * 10 for i, c in enumerate("abcdefgh")}))
    result = train_model(reg, "y", model_type="logistic_regression", task_type="regression",
                         feature_transforms=[{"op": "target_encode", "columns": ["city"]},
                                             {"op": "interaction", "pairs": [["price", "qty"]]}])
    assert result.cv_mean is not None and result.cv_mean > 0.9


def test_target_encoding_does_not_leak_the_label():
    """An ID-like column carries no signal. Encoded inside the pipeline it must score at chance;
    the same encoder fitted on all rows first (the classic mistake) must score far above it."""
    rng = np.random.default_rng(1)
    n = 600
    noise = pd.DataFrame({"customer": [f"c{i}" for i in rng.integers(0, 300, n)]})
    y = pd.Series(rng.integers(0, 2, n), name="y")

    ours = train_model(noise.assign(y=y), "y", model_type="logistic_regression",
                       feature_transforms=[{"op": "target_encode", "columns": ["customer"]}])

    leaked = TargetEncoder(smooth=1.0).fit(noise, y).transform(noise)  # sees every label
    leaky = cross_val_score(LogisticRegression(), leaked, y,
                            cv=StratifiedKFold(5, shuffle=True, random_state=42)).mean()

    assert ours.cv_mean < 0.6
    assert leaky > 0.7


def test_saved_model_loads_where_only_shared_is_importable(df, tmp_path):
    """The deployment service has shared/ but not the training app; the pickle must not need it."""
    result = train_model(df, "y", model_type="random_forest", feature_transforms=ALL_TRANSFORMS)
    path = tmp_path / "model.joblib"
    joblib.dump(result.pipeline, path)
    rows = features(df).head(5)
    rows.to_csv(tmp_path / "rows.csv", index=False)

    script = (
        "import sys, joblib, pandas as pd\n"
        f"sys.path[:] = [{REPO_ROOT!r}] + [p for p in sys.path if 'training-service' not in p]\n"
        f"model = joblib.load({str(path)!r})\n"
        f"print(list(model.predict(pd.read_csv({str(tmp_path / 'rows.csv')!r}))))\n"
    )
    out = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == str(list(result.pipeline.predict(rows)))


def test_every_branch_has_an_input_kind_for_the_schema_endpoint(df):
    X = features(df)
    pre = build_preprocessor(X, ALL_TRANSFORMS).fit(X, df["y"])
    assert {name for name, _, _ in pre.transformers_} - {"remainder"} <= set(BRANCH_INPUT_KIND)


# ── Validation ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("transforms, message", [
    ([{"op": "square", "columns": ["age"]}], "Unknown transform"),
    ([{"op": "log", "columns": ["age"]}, {"op": "log", "columns": ["price"]}], "listed twice"),
    ([{"op": "log", "columns": ["salary"]}], "no such feature"),
    ([{"op": "log", "columns": []}], "at least one column"),
    ([{"op": "log", "columns": ["city"]}], "needs numeric"),
    ([{"op": "bin", "columns": ["age"], "n_bins": 1}], "n_bins"),
    ([{"op": "interaction", "pairs": [["price", "price"]]}], "two different"),
    ([{"op": "datetime_parts", "columns": ["signup"], "parts": ["minute"]}], "parts must come from"),
    ([{"op": "datetime_parts", "columns": ["city"]}], "no dates could be read"),
    ([{"op": "log", "columns": ["age"]}, {"op": "bin", "columns": ["age"]}], "used by both"),
])
def test_invalid_transforms_are_rejected_with_a_clear_message(df, transforms, message):
    with pytest.raises(ValueError, match=message):
        validate_transforms(features(df), transforms)


def test_log_rejects_negative_training_values(df):
    with pytest.raises(ValueError, match="values >= 0"):
        validate_transforms(features(df).assign(income=-1.0), [{"op": "log", "columns": ["income"]}])


def test_target_column_cannot_be_transformed(df):
    with pytest.raises(ValueError, match="no such feature"):
        train_model(df, "y", feature_transforms=[{"op": "log", "columns": ["y"]}])


def test_api_request_carries_transforms_to_training(df):
    from pydantic import ValidationError
    from shared.schemas.training import TrainingRequest

    request = TrainingRequest(dataset_id=1, target_column="y", model_type="random_forest",
                              feature_transforms=ALL_TRANSFORMS)
    passed_on = [t.model_dump(exclude_none=True) for t in request.feature_transforms]  # as the route does
    assert validate_transforms(features(df), passed_on)[0] == {"op": "log", "columns": ["income"]}

    with pytest.raises(ValidationError):
        TrainingRequest(dataset_id=1, target_column="y", model_type="random_forest",
                        feature_transforms=[{"op": "square", "columns": ["age"]}])
