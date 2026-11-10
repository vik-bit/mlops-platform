"""Helpers shared by the v2 measurement scripts (run against the Kind cluster from the host).

The scripts call the services' NodePorts directly (see k8s/kind/kind-config.yaml) rather than going
through the JWT gateway, so they measure the serving path, not authentication.
"""

import io
import json
import os
import subprocess
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

DATASET = os.environ.get("DATASET_URL", "http://localhost:18001")
TRAINING = os.environ.get("TRAINING_URL", "http://localhost:18002")
DEPLOYMENT = os.environ.get("DEPLOYMENT_URL", "http://localhost:18003")
MONITORING = os.environ.get("MONITORING_URL", "http://localhost:18004")
KUBECTL = os.environ.get("KUBECTL", "kubectl")

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = os.path.join(REPO, "docs", "v2-results")
TARGET = "median_house_value"

# A small forest keeps the pickled model a few MB (it is stored in Postgres) and makes each
# prediction cost a few ms of CPU, which is what the HPA reacts to.
RF_PARAMS = {"n_estimators": 60, "max_depth": 12, "min_samples_leaf": 5, "random_state": 42, "n_jobs": 1}


def housing() -> pd.DataFrame:
    """California housing from datasets/housing.csv, minus the 207 rows with no total_bedrooms
    (JSON has no NaN, and the drift parser reads logged inputs back as Python literals)."""
    df = pd.read_csv(os.path.join(REPO, "datasets", "housing.csv"))
    return df.dropna().reset_index(drop=True)


def features(row: pd.Series) -> Dict[str, Any]:
    out = {}
    for k, v in row.items():
        if k == TARGET:
            continue
        out[k] = v.item() if hasattr(v, "item") else v
    return out


def upload(df: pd.DataFrame, name: str) -> int:
    buf = io.BytesIO(df.to_csv(index=False).encode())
    r = requests.post(f"{DATASET}/datasets", files={"file": (name, buf, "text/csv")}, timeout=120)
    r.raise_for_status()
    return r.json()["id"]


def train(dataset_id: int, params: Optional[dict] = None, model_type: str = "random_forest",
          task_type: str = "regression", timeout_s: float = 1200) -> Dict[str, Any]:
    r = requests.post(f"{TRAINING}/train", timeout=60, json={
        "dataset_id": dataset_id, "target_column": TARGET, "model_type": model_type,
        "task_type": task_type, "hyperparameters": params or RF_PARAMS})
    r.raise_for_status()
    job_id = r.json()["id"]
    job = wait_job(job_id, timeout_s)
    models = requests.get(f"{TRAINING}/models", timeout=60).json()
    model = next(m for m in models if m["training_job_id"] == job_id)
    return {"job": job, "model_id": model["id"]}


def wait_job(job_id: int, timeout_s: float = 1200) -> Dict[str, Any]:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        job = requests.get(f"{TRAINING}/training/{job_id}", timeout=30).json()
        if job["status"] in ("completed", "failed", "cancelled"):
            if job["status"] != "completed":
                raise RuntimeError(f"training job {job_id} {job['status']}: {job.get('error_message')}")
            return job
        time.sleep(3)
    raise TimeoutError(f"training job {job_id} did not finish in {timeout_s} s")


def deploy(model_id: int) -> int:
    r = requests.post(f"{DEPLOYMENT}/deploy/{model_id}", timeout=60)
    r.raise_for_status()
    deps = requests.get(f"{DEPLOYMENT}/deployments", timeout=30).json()
    return max(d["id"] for d in deps if d["model_id"] == model_id)


def predict(deployment_id: int, feats: Dict[str, Any], session: Optional[requests.Session] = None):
    s = session or requests
    return s.post(f"{DEPLOYMENT}/deployments/{deployment_id}/predict", json={"features": feats}, timeout=30)


def feedback(deployment_id: int, samples: List[Dict[str, Any]]):
    for i in range(0, len(samples), 500):
        r = requests.post(f"{DEPLOYMENT}/deployments/{deployment_id}/feedback",
                          json={"samples": samples[i:i + 500]}, timeout=120)
        r.raise_for_status()


def set_policy(deployment_id: int, policy: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.put(f"{DEPLOYMENT}/deployments/{deployment_id}/policy", json=policy, timeout=30)
    r.raise_for_status()
    return r.json()


def events(deployment_id: int) -> List[Dict[str, Any]]:
    return list(reversed(requests.get(f"{DEPLOYMENT}/deployments/{deployment_id}/events?limit=500",
                                      timeout=30).json()))


def kubectl_json(*args) -> Dict[str, Any]:
    out = subprocess.run([KUBECTL, *args, "-o", "json"], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def save_json(name: str, data: Any):
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, name), "w") as f:
        json.dump(data, f, indent=2, default=str)
