"""Model lifecycle: rollout decisions, the promotion gate and the retrain trigger.

`policy` is pure Python + numpy (no database, no HTTP) so it can be unit tested without a cluster.
`events` writes lifecycle events to Postgres and is imported only by the services.
"""
