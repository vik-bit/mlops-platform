import json

import numpy as np
import pandas as pd
import pytest

from app.services.profile_dataset import profile_dataset


@pytest.fixture
def write_csv(tmp_path):
    def _write(df):
        path = tmp_path / "data.csv"
        df.to_csv(path, index=False)
        return str(path)
    return _write


def test_basic_counts_and_column_stats(write_csv):
    df = pd.DataFrame({
        "age": [20, 30, None, 50],
        "city": ["a", "b", "a", None],
    })
    profile = profile_dataset(write_csv(df))

    assert profile["row_count"] == 4
    assert profile["column_count"] == 2
    assert profile["missing_cells"] == 2
    assert profile["missing_pct"] == 25.0

    age = profile["columns"]["age"]
    assert age["missing"] == 1 and age["missing_pct"] == 25.0
    assert age["min"] == 20 and age["max"] == 50
    assert age["mean"] == pytest.approx(100 / 3)
    assert age["median"] == 30

    city = profile["columns"]["city"]
    assert city["unique_count"] == 2
    assert city["top_values"][0] == "a"
    assert profile["target"] is None


def test_profile_is_json_serialisable(write_csv):
    # The route returns this dict directly, so numpy scalars or NaN would break the response.
    df = pd.DataFrame({"x": [1.5, 2.5, 3.5], "empty": [np.nan] * 3, "y": [0, 1, 0]})
    profile = profile_dataset(write_csv(df), target_column="y")
    json.dumps(profile, allow_nan=False)
    assert profile["columns"]["empty"]["mean"] is None


def test_classification_target_and_imbalance_warning(write_csv):
    df = pd.DataFrame({"x": range(70), "label": ["yes"] * 60 + ["no"] * 10})
    profile = profile_dataset(write_csv(df), target_column="label")

    target = profile["target"]
    assert target["suggested_task"] == "classification"
    assert target["distribution"] == {"yes": 60, "no": 10}
    assert profile["imbalance_warning"] is not None
    assert "6.0x" in profile["imbalance_warning"]


def test_balanced_target_has_no_imbalance_warning(write_csv):
    df = pd.DataFrame({"x": range(40), "label": [0, 1] * 20})
    profile = profile_dataset(write_csv(df), target_column="label")
    assert profile["imbalance_warning"] is None


def test_many_valued_numeric_target_suggests_regression(write_csv):
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"x": rng.normal(size=100), "price": rng.uniform(0, 1000, 100)})
    profile = profile_dataset(write_csv(df), target_column="price")
    assert profile["target"]["suggested_task"] == "regression"


def test_leakage_hint_for_near_copy_of_target(write_csv):
    rng = np.random.default_rng(0)
    target = rng.uniform(0, 100, 200)
    df = pd.DataFrame({
        "leaky": target * 2 + 1,
        "noise": rng.normal(size=200),
        "price": target,
    })
    warnings = profile_dataset(write_csv(df), target_column="price")["warnings"]
    assert any("leaky" in w and "leakage" in w for w in warnings)
    assert not any("noise" in w for w in warnings)


def test_missing_target_values_are_warned(write_csv):
    df = pd.DataFrame({"x": range(6), "label": [0, 1, None, 0, 1, None]})
    profile = profile_dataset(write_csv(df), target_column="label")
    assert profile["target"]["missing"] == 2
    assert any("2 missing values" in w for w in profile["warnings"])


def test_unknown_target_column_is_reported(write_csv):
    profile = profile_dataset(write_csv(pd.DataFrame({"x": [1, 2]})), target_column="nope")
    assert profile["target"] is None
    assert profile["warnings"] == ["Target column 'nope' not found in dataset"]


def test_header_only_csv(write_csv):
    profile = profile_dataset(write_csv(pd.DataFrame({"a": [], "b": []})))
    assert profile["row_count"] == 0
    assert profile["missing_pct"] == 0
    assert profile["columns"]["a"]["missing_pct"] == 0
