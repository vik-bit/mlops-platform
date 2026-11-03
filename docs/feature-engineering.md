# Feature engineering

Every model is trained as one scikit-learn pipeline, `preprocessor → model`, and the whole pipeline
is saved in the registry. Whatever happens to the data in training happens the same way at
prediction time, and cross-validation refits every step on each training fold.

## Default preprocessing (always on)

| Column type | Steps |
|---|---|
| Numeric | missing → median, then scaled to mean 0, std 1 |
| Text, category, bool | missing → most frequent value, then one-hot (categories not seen in training are ignored) |

## Transforms you can add

`POST /train` accepts an optional `feature_transforms` list. Each op may appear once, and can list
several columns:

```json
{
  "dataset_id": 3, "target_column": "churned", "model_type": "random_forest",
  "feature_transforms": [
    {"op": "log",            "columns": ["income"]},
    {"op": "bin",            "columns": ["age"], "n_bins": 5},
    {"op": "datetime_parts", "columns": ["signup_date"], "parts": ["month", "dayofweek", "hour"]},
    {"op": "interaction",    "pairs": [["price", "quantity"]]},
    {"op": "target_encode",  "columns": ["city"]}
  ]
}
```

| Op | Input | What it produces | Replaces the default? |
|---|---|---|---|
| `log` | numeric, ≥ 0 | `log(1 + x)`, scaled. Negative values at prediction time are clipped to 0 | yes |
| `bin` | numeric | One-hot quantile bins (`n_bins`, default 5). Bins that collapse on tied values are merged | yes |
| `datetime_parts` | date/time text | `year`, `month`, `day`, `dayofweek` and `hour` (choose with `parts`), scaled. Unreadable dates are imputed | yes |
| `interaction` | numeric pairs | The product of each pair, scaled | no: the columns also keep their default branch |
| `target_encode` | categorical | The category's average label (one column per class for multiclass), scaled | yes |

The API rejects an unknown op with a 422. Everything else is checked against the dataset before
training starts: missing columns, the wrong column type, negative values for `log`, dates that
can't be read, and a column claimed by two replacing ops. Any of these fails the job with a
message saying what to fix. The checked list, with
defaults filled in, is saved in the model's metadata (`feature_transforms`).

Engineered features show up under their own names in feature importance and SHAP, for example
`log__income`, `date__signup_date_hour` and `interaction__price*quantity`. The deployment
service's `/predict/{id}/schema` still lists the raw input columns, each with its kind: numeric,
categorical or datetime.

## Target encoding and leakage

Target encoding replaces a category with the average label for that category. Done naively (fit
on all the data, then cross-validate), it leaks: each row's encoding already contains its own
label. Here it sits inside the pipeline, so cross-validation fits it only on the training folds.
scikit-learn's `TargetEncoder` also cross-fits within the training data (seeded 5-fold).

`test_target_encoding_does_not_leak_the_label` checks this on a column that carries no signal
(customer IDs, random labels):

| How the ID column is encoded | 5-fold CV accuracy |
|---|---|
| Fitted on all rows first (the leak) | 76.2% |
| Inside the pipeline (this platform) | 50.2%, which is chance |

## Does it help? A measurement

`backend/training-service/scripts/feature_benchmark.py` trains on the Adult census income data
(OpenML 1590, 48,842 rows, 23.9% positive) with and without one transform set. I fixed that set
before the first run, for the usual reasons:

- `log` on capital gain and capital loss (heavily skewed)
- `bin` on age and hours per week (8 bins)
- `target_encode` on native country and occupation
- an `interaction` of education × hours per week

Both pipelines used the same 5 folds, so the differences are paired.

| Model | Default preprocessing | With the transforms | Difference (range over folds) |
|---|---|---|---|
| Logistic regression | 85.14% ± 0.27% | 84.89% ± 0.30% | −0.25 pts (−0.44 to −0.02) |
| Random forest | 85.32% ± 0.36% | 85.56% ± 0.29% | +0.24 pts (+0.00 to +0.36) |

<sub>One run, 3 November 2026, scikit-learn 1.9, in the training-service image.</sub>

On this dataset the transforms barely matter:
- **Random forest:** a quarter of a point better, and no worse on any fold.
- **Logistic regression:** a quarter of a point worse on every fold. Binning age and hours, and
  target-encoding occupation, take away detail that its one-hot and scaled inputs already used.
- **Hours per week** has so many ties at 40 that 3 of its 8 quantile bins collapse, leaving 5.

The point of the feature is a correct, leak-free place to put such transforms, not a guaranteed
gain: which transforms help depends on the data and the model, and is best checked with the
`/jobs/compare` endpoint.
