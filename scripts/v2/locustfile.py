"""Locust load for POST /deployments/{id}/predict with a staged ramp (see StepLoad.stages).

Run headless by scripts/v2/load_test.py, which also samples the HPA and pods. Every request's
start time, latency and status is appended to REQUEST_LOG so p95 can be computed per time bucket
from raw samples instead of Locust's running aggregates.
"""

import csv
import os
import random
import sys
import time

from locust import FastHttpUser, LoadTestShape, constant, events, task

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c  # noqa: E402

DEPLOYMENT_ID = int(os.environ["DEPLOYMENT_ID"])
REQUEST_LOG = os.environ.get("REQUEST_LOG", "requests.csv")
ROWS = [c.features(r) for _, r in c.housing().sample(2000, random_state=1).iterrows()]

_log = open(REQUEST_LOG, "w", newline="")
_writer = csv.writer(_log)
_writer.writerow(["t", "latency_ms", "ok"])


@events.request.add_listener
def _record(request_type, name, response_time, response_length, exception, start_time=None, **kw):
    _writer.writerow([round(start_time or time.time(), 3), round(response_time, 2), int(exception is None)])


@events.quitting.add_listener
def _close(environment, **kw):
    _log.close()


class Client(FastHttpUser):
    wait_time = constant(0.1)  # each user sends up to ~10 req/s; the server's latency throttles it

    @task
    def predict(self):
        self.client.post(f"/deployments/{DEPLOYMENT_ID}/predict",
                         json={"features": random.choice(ROWS)}, name="predict")


class StepLoad(LoadTestShape):
    # (duration of the stage in s, concurrent users)
    stages = [(60, 2), (120, 8), (180, 16), (180, 24), (180, 8), (180, 1)]

    def tick(self):
        t = self.get_run_time()
        for duration, users in self.stages:
            if t < duration:
                return users, max(users, 4)
            t -= duration
        return None
