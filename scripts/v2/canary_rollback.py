"""Plant bad models behind a canary and measure how fast the controller rolls them back.

Scenarios (each a 20 % canary against the same stable random forest on California housing):
  schema_break   trained with an extra column live requests never carry -> every candidate request 500s
  shuffled_label trained on permuted targets -> answers 200 with plausible-looking but wrong values
  healthy        same recipe, different seed -> control: must NOT be rolled back

Steady traffic (TARGET_RPS from a thread pool) runs throughout. Per scenario we record the
server's rollout start/end times and, client-side, every response (status, which arm answered).

    python scripts/v2/canary_rollback.py        # writes docs/v2-results/canary_rollback.json
"""

import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import numpy as np
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c  # noqa: E402

TARGET_RPS = float(os.environ.get("TARGET_RPS", "25"))
CANARY_PCT = float(os.environ.get("CANARY_PCT", "20"))
HEALTHY_WATCH_S = float(os.environ.get("HEALTHY_WATCH_S", "90"))
TIMEOUT_S = 180


class Traffic:
    """Open-loop-ish load: one request every 1/TARGET_RPS s, each on a pool thread."""

    def __init__(self, deployment_id, rows):
        self.dep, self.rows = deployment_id, rows
        self.log = []  # (t, status, arm, model_id)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=32)
        self._session = requests.Session()
        self._session.mount("http://", requests.adapters.HTTPAdapter(pool_maxsize=32))

    def _one(self, feats):
        t = time.time()
        try:
            r = c.predict(self.dep, feats, self._session)
            body = r.json() if r.status_code == 200 else {}
            rec = (t, r.status_code, body.get("arm"), body.get("model_id"))
        except Exception:
            rec = (t, -1, None, None)
        with self._lock:
            self.log.append(rec)

    def _run(self):
        i, period, nxt = 0, 1.0 / TARGET_RPS, time.time()
        while not self._stop.is_set():
            self._pool.submit(self._one, c.features(self.rows.iloc[i % len(self.rows)]))
            i += 1
            nxt += period
            time.sleep(max(0.0, nxt - time.time()))

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stop.set()
        self._pool.shutdown(wait=True)

    def window(self, t0, t1):
        with self._lock:
            return [x for x in self.log if t0 <= x[0] <= t1]


def ts(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def run_scenario(traffic, dep, name, model_id):
    t_req = time.time()
    r = requests.post(f"{c.DEPLOYMENT}/deployments/{dep}/rollouts", timeout=60, json={
        "candidate_model_id": model_id, "mode": "canary", "traffic_percent": CANARY_PCT,
        "actor": "canary_rollback.py", "reason": f"planted: {name}"})
    r.raise_for_status()
    rollout = r.json()
    rid = rollout["id"]
    watch = HEALTHY_WATCH_S if name == "healthy" else TIMEOUT_S
    status = rollout
    while time.time() - t_req < watch:
        status = requests.get(f"{c.DEPLOYMENT}/rollouts/{rid}", timeout=30).json()
        if status["status"] != "active":
            break
        time.sleep(0.5)
    if status["status"] == "active":  # healthy control: end it by hand
        requests.post(f"{c.DEPLOYMENT}/rollouts/{rid}/cancel", timeout=30)
    time.sleep(5)  # keep traffic flowing to see whether any request still reaches the candidate
    status = requests.get(f"{c.DEPLOYMENT}/rollouts/{rid}", timeout=30).json()

    started = ts(status["started_at"])
    ended = ts(status["ended_at"]) if status["ended_at"] else None
    seen = traffic.window(started - 1, time.time())
    during = [x for x in seen if x[0] <= (ended or time.time())]
    cand = [x for x in during if x[2] == "candidate"]
    errs = [x for x in during if x[1] != 200]
    after = [x for x in seen if ended and x[0] > ended]
    after_cand = [x for x in after if x[2] == "candidate" or x[1] != 200]
    return {
        "scenario": name,
        "rollout_id": rid,
        "candidate_model_id": model_id,
        "outcome": status["status"],
        "decision_reason": status["decision_reason"],
        "time_to_decision_s": round(ended - started, 2) if ended else None,
        "requests_during_rollout": len(during),
        "candidate_answered_200": len(cand),
        "client_errors": len(errs),
        "requests_affected": len(cand) + len(errs),
        "affected_after_decision": len(after_cand),
        "server_served": status.get("served"),
        "last_metrics": status.get("last_metrics"),
    }


def main():
    df = c.housing()
    rng = np.random.default_rng(0)
    order = rng.permutation(len(df))
    train_df, live_df = df.iloc[order[: int(0.8 * len(df))]], df.iloc[order[int(0.8 * len(df)):]]

    print("training stable, healthy, schema_break and shuffled_label models ...")
    stable = c.train(c.upload(train_df, "housing_train.csv"))["model_id"]
    healthy = c.train(c.upload(train_df, "housing_train_seed7.csv"),
                      params={**c.RF_PARAMS, "random_state": 7})["model_id"]
    broken_df = train_df.assign(rooms_per_household=train_df.total_rooms / train_df.households)
    schema_break = c.train(c.upload(broken_df, "housing_extra_column.csv"))["model_id"]
    shuffled_df = train_df.assign(**{c.TARGET: rng.permutation(train_df[c.TARGET].to_numpy())})
    shuffled = c.train(c.upload(shuffled_df, "housing_shuffled_target.csv"))["model_id"]
    dep = c.deploy(stable)
    print(f"deployment {dep}: stable={stable} healthy={healthy} schema_break={schema_break} shuffled={shuffled}")

    traffic = Traffic(dep, live_df.reset_index(drop=True))
    traffic.start()
    time.sleep(20)  # warm-up: every pod loads the stable model, the stable arm gets a baseline
    results = []
    try:
        for name, mid in (("schema_break", schema_break), ("shuffled_label", shuffled), ("healthy", healthy)):
            print(f"-- {name}")
            res = run_scenario(traffic, dep, name, mid)
            print(res)
            results.append(res)
            time.sleep(10)
    finally:
        traffic.stop()

    c.save_json("canary_rollback.json", {
        "target_rps": TARGET_RPS, "canary_percent": CANARY_PCT, "deployment_id": dep,
        "stable_model_id": stable, "thresholds": results and requests.get(
            f"{c.DEPLOYMENT}/rollouts/{results[0]['rollout_id']}", timeout=30).json()["thresholds"],
        "results": results, "events": c.events(dep)})


if __name__ == "__main__":
    main()
