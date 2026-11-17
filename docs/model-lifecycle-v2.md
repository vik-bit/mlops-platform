# v2 model lifecycle: rollouts, rollback, drift-triggered retraining

v1 could train a model and deploy it. v2 adds the operations around a deployed model: putting a new
version in front of live traffic safely, taking it out again automatically when it misbehaves, and
retraining when the inputs drift away from what the model was trained on.

```
             ┌──────────── deployment-service ─────────────┐
 client ───► │ POST /deployments/{id}/predict               │
             │   choose_arm: stable | candidate (canary %)  │──► prediction logs (async, batched)
             │   shadow: candidate scored off-path, logged  │          │
             │ RolloutController (every 2 s, each pod)      │◄─────────┘ reads both arms' logs
             │   evaluate_rollout → rollback / promote      │──► lifecycle_events
             └──────────────────────────────────────────────┘
                     ▲ promote / start canary
                     │
 training-service  POST /retrain: train on recent labelled rows, gate vs live on newest rows
                     ▲
 monitoring-service RetrainController (every 15 s): compute_drift on recent inputs → should_retrain
```

All decisions are pure functions in [`shared/lifecycle/policy.py`](../shared/lifecycle/policy.py),
tested without a database or cluster. The services only gather inputs for them and act on the result.

## Serving through a deployment

`POST /deployments/{id}/predict` is the stable client endpoint. The deployment row says which model
is stable; an active rollout (at most one per deployment) adds a candidate. Each pod caches the
route for `ROUTING_TTL_S` (1 s on Kind), so a rollback or promotion reaches every pod within about
a second. The v1 per-model endpoints (`/predict/{model_id}/named` and so on) still work.

- **Shadow**: the stable model answers. The candidate scores the same input on a small thread pool
  (at most 64 in flight; overflow is skipped and counted in `deployment_shadow_skipped_total`), and
  its result is logged but never returned.
- **Canary**: each request goes to the candidate with probability `traffic_percent`, independently
  per request (no stickiness).

Two v1 behaviours changed on the way, because they would have dominated any latency number:
pipelines are now cached per process (v1 unpickled the model from Postgres on every request), and
prediction logs go through a bounded in-process queue that a background thread posts to
`/log/batch` (v1 made a blocking HTTP call per prediction with a 30 s timeout). If the queue is
full, log lines are dropped and counted rather than slowing predictions; `GET /lifecycle/status`
shows the counters.

## Automatic rollback

Every `ROLLOUT_EVAL_INTERVAL_S` each deployment-service pod reads both arms' prediction logs since
the rollout started and calls `evaluate_rollout`. A rollout is rolled back when, after at least
`min_requests` candidate requests, any of these holds (all breaches are recorded, not just the first):

| Rule | Default |
|---|---|
| candidate error rate | > 5 % |
| candidate p95 inference latency | > 500 ms |
| candidate p95 / stable p95 | > 3x (once the stable arm has `min_requests` samples) |
| PSI of candidate predictions vs stable predictions in the same window | > 0.25 |

The last rule catches a model that answers 200 with wrong values: its outputs are distributed
differently from the stable model's on the same traffic. It cannot catch a model whose output
distribution looks right but is wrong row by row; only labels can, which is what the retrain gate uses.

With `auto_promote`, a rollout that stays healthy for `promote_after_requests` candidate requests is
promoted (a shadow rollout moves to a canary at `canary_percent_after_shadow` first). Without it, a
person promotes from the UI or `POST /rollouts/{id}/promote`.

The rollback/promotion is a conditional `UPDATE ... WHERE status = 'active'`, so when several
replicas evaluate the same rollout only one records the event.

## Drift-triggered retraining

When a deployment's policy has `retrain.enabled`, the monitoring service checks it every
`RETRAIN_CHECK_INTERVAL_S`:

1. `compute_drift` (the existing [drift.py](../backend/monitoring-service/app/services/drift.py))
   compares the last `window` logged inputs with the model's training baseline, now read from the
   registry instead of a file path.
2. `should_retrain` fires when the overall PSI, any feature's PSI or any feature's KS statistic
   crosses its threshold, there are at least `min_labelled` labelled samples, no retrain for the
   deployment is running, and `cooldown_s` has passed since the last one.
3. It records `drift_detected` and `retrain_queued` events and calls `POST /retrain`.

Labels come from `POST /deployments/{id}/feedback` (`{"samples": [{"features": ..., "label": ...}]}`).

The retrain job takes the deployment's most recent `labelled_window` labelled rows in arrival order,
holds out the newest `holdout_fraction`, trains a candidate with the live model's recipe (model
type, hyperparameters, feature transforms), and scores both models on the held-out rows. The
**promotion gate** passes when the candidate's metric is not worse than the live model's by more
than `margin` (absolute; the direction is handled for rmse/mae), with at least `min_holdout`
held-out rows. Passing candidates are promoted directly or started as a canary (`promote_mode`);
failing ones are kept in the registry as `rejected`. `gate_passed` / `gate_failed` events carry both
scores.

The KS statistic compares inputs against a normal with the baseline mean and standard deviation, so
skewed features score 0.1 to 0.2 even without drift (measured on held-out housing rows). The default
KS threshold of 0.3 sits above that.

## Policy

`GET/PUT /deployments/{id}/policy` stores per-deployment overrides as JSON; anything not set uses
the dataclass defaults in `policy.py`. Changing policy, rollouts and promotions through the gateway
needs the admin role; predictions and feedback do not.

```json
{
  "retrain": {"enabled": true, "psi_threshold": 0.2, "feature_psi_threshold": 0.25, "ks_threshold": 0.3,
              "window": 500, "min_samples": 100, "min_labelled": 300, "labelled_window": 2000,
              "holdout_fraction": 0.3, "cooldown_s": 600, "promote_mode": "direct", "canary_percent": 10},
  "gate":    {"metric": "rmse", "margin": 0.0, "min_holdout": 50},
  "rollout": {"max_error_rate": 0.05, "max_p95_latency_ms": 500, "max_p95_ratio": 3.0,
              "max_prediction_psi": 0.25, "min_requests": 20, "auto_promote": false,
              "promote_after_requests": 300, "canary_percent_after_shadow": 10}
}
```

## Events

`lifecycle_events` is append-only: `deployed`, `undeployed`, `shadow_started`, `canary_started`,
`shadow_passed`, `promoted`, `rolled_back`, `rollout_cancelled`, `drift_detected`, `retrain_queued`,
`gate_passed`, `gate_failed`, `retrain_failed`, `promotion_failed`. The Deployments page shows them
per deployment (Rollouts & events), and `GET /events` lists them all.

## Known limits

- Rollout metrics come from the prediction logs, which arrive about 0.5 s after serving (batched
  flush), and the controller runs every 2 s, so time to rollback has a floor of a few seconds.
- The stable arm's statistics include any other traffic to the same model id in the window.
- Canary assignment is per request, not per user.
- Retraining runs in a thread inside the training-service pod, not in a separate job/queue; a pod
  restart loses an in-flight retrain. Its job stays `running`, and after `RETRAIN_MAX_RUNTIME_S`
  (30 min) the monitoring service stops treating it as in flight.
