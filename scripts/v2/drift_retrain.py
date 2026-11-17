"""Injected covariate shift on California housing: detect -> retrain -> gated promotion.

The live model is a random forest trained only on Southern California (latitude < 35). Traffic
first comes from held-out southern rows, then switches to a shifted stream. Every prediction's
true label is sent back as feedback right away (in production labels arrive later; here that
delay is zero). The monitoring service's controller checks drift every RETRAIN_CHECK_INTERVAL_S,
queues a retrain on the most recent labelled rows, and the training service promotes the candidate
only if its RMSE on the newest 30 % of those rows is not worse than the live model's.

Scenarios:
  north         traffic moves to Northern California (a region the live model never saw)
  high_income   traffic stays in the south but only from tracts above the median income
                (a milder shift: the gate decides whether retraining on fewer rows actually helps)

    python scripts/v2/drift_retrain.py      # writes docs/v2-results/drift_retrain.json
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import numpy as np
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c  # noqa: E402

RPS = float(os.environ.get("TARGET_RPS", "25"))
POLICY = {
    "retrain": {"enabled": True, "window": 500, "min_samples": 100, "psi_threshold": 0.2,
                "feature_psi_threshold": 0.25, "ks_threshold": 0.3, "min_labelled": 2500,
                "labelled_window": 3000, "holdout_fraction": 0.3, "cooldown_s": 3600,
                "promote_mode": "direct"},
    "gate": {"metric": "rmse", "margin": 0.0, "min_holdout": 200},
}
TERMINAL = {"promoted", "gate_failed", "retrain_failed", "promotion_failed"}


def ts(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def stream(dep, rows, pool, stop_when=None, max_rows=None):
    """Send rows at RPS with feedback; returns [(t, y_true, y_pred, model_id)]."""
    out, batch, futures = [], [], []
    period, nxt = 1.0 / RPS, time.time()
    session = requests.Session()
    session.mount("http://", requests.adapters.HTTPAdapter(pool_maxsize=16))

    def one(row):
        feats = c.features(row)
        t = time.time()
        r = c.predict(dep, feats, session)
        body = r.json() if r.status_code == 200 else {}
        return t, float(row[c.TARGET]), body.get("prediction"), body.get("model_id"), feats

    for i, (_, row) in enumerate(rows.iterrows()):
        if max_rows and i >= max_rows:
            break
        futures.append(pool.submit(one, row))
        nxt += period
        time.sleep(max(0.0, nxt - time.time()))
        if len(futures) >= 100:
            for f in futures:
                t, y, p, mid, feats = f.result()
                out.append((t, y, p, mid))
                batch.append({"features": feats, "label": y})
            futures = []
            c.feedback(dep, batch)
            batch = []
            if stop_when and stop_when():
                break
    for f in futures:
        t, y, p, mid, feats = f.result()
        out.append((t, y, p, mid))
        batch.append({"features": feats, "label": y})
    if batch:
        c.feedback(dep, batch)
    return out


def rmse(recs):
    pairs = [(y, p) for _, y, p, _ in recs if p is not None]
    return round(float(np.sqrt(np.mean([(y - p) ** 2 for y, p in pairs]))), 1) if pairs else None


def check(dep):
    return requests.post(f"{c.MONITORING}/deployments/{dep}/lifecycle-check", timeout=60).json()


def scenario(name, live_train, south_live, shifted, pool):
    model = c.train(c.upload(live_train, f"housing_south_train_{name}.csv"))["model_id"]
    dep = c.deploy(model)
    c.set_policy(dep, POLICY)
    print(f"[{name}] deployment {dep}, live model {model}")

    a = stream(dep, south_live, pool, max_rows=800)
    time.sleep(2)
    check_a = check(dep)
    print(f"[{name}] in-distribution: retrain={check_a['retrain']} overall PSI={check_a['drift']['overall_psi']}")

    t_shift = time.time()
    terminal = lambda: any(e["event_type"] in TERMINAL for e in c.events(dep))  # noqa: E731
    b = stream(dep, shifted, pool, stop_when=terminal, max_rows=6000)
    deadline = time.time() + 600
    while not terminal() and time.time() < deadline:  # retrain may still be running
        time.sleep(3)
    evs = c.events(dep)
    promoted = next((e for e in evs if e["event_type"] == "promoted"), None)

    after = []
    if promoted:
        after = stream(dep, shifted.iloc[len(b):], pool, max_rows=800)
        time.sleep(2)
    check_end = check(dep)

    def at(kind):
        e = next((e for e in evs if e["event_type"] == kind), None)
        return round(ts(e["created_at"]) - t_shift, 1) if e else None

    gate = next((e for e in evs if e["event_type"] in ("gate_passed", "gate_failed")), None)
    t_promote = ts(promoted["created_at"]) if promoted else None
    before = [r for r in b if r[3] == model]
    return {
        "scenario": name,
        "deployment_id": dep,
        "live_model_id": model,
        "in_distribution_check": {"retrain": check_a["retrain"], "breaches": check_a["breaches"],
                                  "drift": check_a["drift"]},
        "shifted_requests_sent": len(b),
        "seconds_after_shift": {"drift_detected": at("drift_detected"), "retrain_queued": at("retrain_queued"),
                                "gate_decided": at("gate_passed") or at("gate_failed"),
                                "promoted": at("promoted")},
        "drift_event": next((e for e in evs if e["event_type"] == "drift_detected"), None),
        "gate": gate and gate["details"],
        "gate_reason": gate and gate["reason"],
        "online_rmse": {"in_distribution": rmse(a),
                        "shifted_live_model": rmse(before),
                        "shifted_after_promotion": rmse(after) if promoted else None},
        "post_check": {"model_id": check_end.get("model_id"), "retrain": check_end.get("retrain"),
                       "drift": check_end.get("drift")},
        "promoted_after_s": round(t_promote - t_shift, 1) if t_promote else None,
        "events": evs,
    }


def main():
    df = c.housing()
    south = df[df.latitude < 35].sample(frac=1, random_state=0)
    north = df[df.latitude >= 35].sample(frac=1, random_state=0)

    # north: live model on 80 % of the south; in-distribution traffic from the other 20 %.
    cut = int(0.8 * len(south))
    north_case = (south.iloc[:cut], south.iloc[cut:], north)

    # high_income: live model on half of the south. The other half is never trained on: 800 of
    # its rows (all incomes) are the in-distribution phase, then its remaining above-median-income
    # rows are the shifted stream. No row is sent twice, so the retrain's held-out rows are unseen.
    half = len(south) // 2
    train_half, other = south.iloc[:half], south.iloc[half:]
    phase_a = other.iloc[:800]
    rest = other.iloc[800:]
    high = rest[rest.median_income > south.median_income.median()]
    income_case = (train_half, phase_a, high)

    results = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        for name, (live_train, in_dist, shifted) in (("north", north_case), ("high_income", income_case)):
            res = scenario(name, live_train, in_dist, shifted, pool)
            print({k: v for k, v in res.items() if k not in ("events", "post_check", "in_distribution_check")})
            results.append(res)
    c.save_json("drift_retrain.json", {"rps": RPS, "policy": POLICY, "results": results})


if __name__ == "__main__":
    main()
