"""Prediction logging to the monitoring service, off the request path.

v1 made one blocking HTTP call per prediction (30 s timeout), so a slow monitoring service slowed
every prediction. Now predictions go into a bounded in-process queue and a daemon thread posts them
to /log/batch in batches. If the queue is full the log line is dropped and counted rather than
blocking the caller; `stats()` exposes the counters.

The rollout controller and drift detection read these logs, so they see a prediction roughly
FLUSH_INTERVAL_S after it was served.
"""

import os
import queue
import threading
import time

import requests

MONITORING_URL = os.environ.get("MONITORING_SERVICE_URL", "http://monitoring-service:8000")
FLUSH_INTERVAL_S = float(os.environ.get("LOG_FLUSH_INTERVAL_S", "0.5"))
BATCH_SIZE = int(os.environ.get("LOG_BATCH_SIZE", "200"))
QUEUE_MAX = int(os.environ.get("LOG_QUEUE_MAX", "20000"))

_queue: "queue.Queue[dict]" = queue.Queue(maxsize=QUEUE_MAX)
_counters = {"queued": 0, "sent": 0, "dropped": 0, "failed_batches": 0}
_lock = threading.Lock()
_started = False


def _bump(key: str, n: int = 1):
    with _lock:
        _counters[key] += n


def stats() -> dict:
    with _lock:
        return {**_counters, "pending": _queue.qsize()}


def _post(batch):
    try:
        r = requests.post(f"{MONITORING_URL}/log/batch", json={"logs": batch}, timeout=10)
        r.raise_for_status()
        _bump("sent", len(batch))
    except Exception as e:  # monitoring down: drop the batch, keep serving
        _bump("failed_batches")
        _bump("dropped", len(batch))
        print("Prediction log batch failed:", repr(e))


def _worker():
    while True:
        batch = []
        deadline = time.monotonic() + FLUSH_INTERVAL_S
        while len(batch) < BATCH_SIZE:
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                break
            try:
                batch.append(_queue.get(timeout=timeout))
            except queue.Empty:
                break
        if batch:
            _post(batch)


def _ensure_started():
    global _started
    if _started:
        return
    with _lock:
        if _started:
            return
        threading.Thread(target=_worker, name="prediction-log-flusher", daemon=True).start()
        _started = True


def log_prediction(model_id, input_data, prediction, latency_ms, status="success"):
    """Queue one prediction log line; never blocks and never raises."""
    _ensure_started()
    try:
        _queue.put_nowait({
            "model_id": int(model_id),
            "input_data": str(input_data),
            "prediction": str(prediction),
            "latency_ms": float(latency_ms),
            "status": status,
        })
        _bump("queued")
    except queue.Full:
        _bump("dropped")
