"""HPA load test: run the Locust ramp against the deployment service and sample the HPA every 5 s.

    python scripts/v2/load_test.py [deployment_id]

With no deployment id it trains and deploys the housing random forest first. Writes
docs/v2-results/load_test.json (per-10 s buckets: rps, p50/p95, errors, replicas) and
docs/v2-results/load_test.png.
"""

import csv
import os
import subprocess
import sys
import threading
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BUCKET_S = 10


def sample_hpa(stop, out):
    while not stop.is_set():
        t = time.time()
        try:
            hpa = c.kubectl_json("-n", "mlops", "get", "hpa", "deployment-service")
            pods = c.kubectl_json("-n", "mlops", "get", "pods", "-l", "app=deployment-service")
            ready = sum(
                1 for p in pods["items"]
                if any(cond["type"] == "Ready" and cond["status"] == "True"
                       for cond in p["status"].get("conditions", [])))
            cur = (hpa["status"].get("currentMetrics") or [{}])[0].get("resource", {}).get("current", {})
            out.append({"t": t, "desired": hpa["status"].get("desiredReplicas"),
                        "current": hpa["status"].get("currentReplicas"), "ready": ready,
                        "cpu_util": cur.get("averageUtilization")})
        except Exception as e:
            out.append({"t": t, "error": repr(e)})
        stop.wait(5)


def main():
    if len(sys.argv) > 1:
        dep = int(sys.argv[1])
    else:
        model = c.train(c.upload(c.housing(), "housing_full.csv"))["model_id"]
        dep = c.deploy(model)
    print(f"load testing deployment {dep}")
    req_log = os.path.join(c.RESULTS, "load_test_requests.csv")
    os.makedirs(c.RESULTS, exist_ok=True)

    hpa_samples, stop = [], threading.Event()
    threading.Thread(target=sample_hpa, args=(stop, hpa_samples), daemon=True).start()
    t_start = time.time()
    env = {**os.environ, "DEPLOYMENT_ID": str(dep), "REQUEST_LOG": req_log}
    subprocess.run([sys.executable, "-m", "locust", "-f", os.path.join(HERE, "locustfile.py"),
                    "--headless", "--host", c.DEPLOYMENT, "--only-summary"], env=env, check=False)
    time.sleep(60)  # watch scale-down settle
    stop.set()

    rows = []
    with open(req_log) as f:
        for r in csv.DictReader(f):
            rows.append((float(r["t"]), float(r["latency_ms"]), int(r["ok"])))
    rows.sort()
    t0 = t_start
    end = max(rows[-1][0], hpa_samples[-1]["t"]) if rows else time.time()
    buckets = []
    for b0 in np.arange(t0, end, BUCKET_S):
        sel = [x for x in rows if b0 <= x[0] < b0 + BUCKET_S]
        hs = [h for h in hpa_samples if b0 <= h["t"] < b0 + BUCKET_S and "ready" in h]
        lat = [x[1] for x in sel if x[2]]
        buckets.append({
            "t_s": int(b0 - t0),
            "rps": round(len(sel) / BUCKET_S, 1),
            "p50_ms": round(float(np.percentile(lat, 50)), 1) if lat else None,
            "p95_ms": round(float(np.percentile(lat, 95)), 1) if lat else None,
            "errors": sum(1 for x in sel if not x[2]),
            "ready_replicas": hs[-1]["ready"] if hs else None,
            "desired_replicas": hs[-1]["desired"] if hs else None,
            "cpu_util_pct": hs[-1]["cpu_util"] if hs else None,
        })
    ok = [x for x in rows if x[2]]
    summary = {"requests": len(rows), "errors": len(rows) - len(ok),
               "p95_ms_overall": round(float(np.percentile([x[1] for x in ok], 95)), 1) if ok else None,
               "max_ready_replicas": max((h.get("ready") or 0) for h in hpa_samples)}
    c.save_json("load_test.json", {"deployment_id": dep, "bucket_s": BUCKET_S, "summary": summary,
                                   "buckets": buckets, "hpa_samples": hpa_samples})
    print(summary)
    plot(buckets)


def plot(buckets):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = [b["t_s"] for b in buckets]
    fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    ax[0].plot(t, [b["rps"] for b in buckets], color="#3b6fb6")
    ax[0].set_ylabel("requests / s")
    ax[1].plot(t, [b["p95_ms"] for b in buckets], color="#c0504d", label="p95")
    ax[1].plot(t, [b["p50_ms"] for b in buckets], color="#9bbb59", label="p50")
    ax[1].set_ylabel("latency (ms)")
    ax[1].legend()
    ax[2].step(t, [b["ready_replicas"] for b in buckets], where="post", color="#4f4f4f", label="ready pods")
    ax[2].step(t, [b["desired_replicas"] for b in buckets], where="post", color="#f79646",
               linestyle="--", label="HPA desired")
    ax[2].set_ylabel("replicas")
    ax[2].set_xlabel("seconds since start")
    ax[2].legend()
    for a in ax:
        a.grid(alpha=0.3)
    fig.suptitle("deployment-service under a stepped Locust load (Kind, laptop)")
    fig.tight_layout()
    fig.savefig(os.path.join(c.RESULTS, "load_test.png"), dpi=110)


if __name__ == "__main__":
    main()
