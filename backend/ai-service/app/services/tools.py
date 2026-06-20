import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _tool(name: str, description: str, properties: Dict[str, Any], required: Optional[List[str]] = None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
            },
        },
    }


COPILOT_TOOLS: List[Dict[str, Any]] = [
    # ── MLflow ────────────────────────────────────────────────────────────────
    _tool(
        "mlflow_list_experiments",
        "List all MLflow experiments in the tracking server.",
        {},
    ),
    _tool(
        "mlflow_search_runs",
        "Search MLflow runs for an experiment. Returns run IDs, metrics, params, and status.",
        {
            "experiment_name": {
                "type": "string",
                "description": "Experiment name (default: training-service)",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum runs to return (default 20)",
            },
        },
    ),
    _tool(
        "mlflow_get_run",
        "Get detailed metrics and parameters for a specific MLflow run.",
        {
            "run_id": {"type": "string", "description": "MLflow run ID"},
        },
        required=["run_id"],
    ),
    # ── Prometheus ──────────────────────────────────────────────────────────────
    _tool(
        "prometheus_query",
        "Run a PromQL instant query against Prometheus. "
        "Examples: monitoring_requests_total, system_cpu_usage_percent, rate(monitoring_requests_total[5m])",
        {
            "query": {"type": "string", "description": "PromQL expression"},
        },
        required=["query"],
    ),
    _tool(
        "prometheus_get_platform_metrics",
        "Get parsed platform metrics from Prometheus and the monitoring service system overview "
        "(CPU, memory, disk, service health, request counts).",
        {},
    ),
    # ── Deployment service ──────────────────────────────────────────────────────
    _tool(
        "list_deployments",
        "List all active model deployments with model IDs, status, and endpoints.",
        {},
    ),
    _tool(
        "get_model_schema",
        "Get the input feature schema for a deployed model (numeric/categorical features).",
        {
            "model_id": {"type": "integer", "description": "Registered model ID"},
        },
        required=["model_id"],
    ),
    # ── Training service ────────────────────────────────────────────────────────
    _tool(
        "list_training_jobs",
        "List all training jobs with status, metrics, and MLflow run IDs.",
        {
            "limit": {
                "type": "integer",
                "description": "Max jobs to return (default 20)",
            },
        },
    ),
    _tool(
        "get_training_job",
        "Get details for a specific training job including accuracy, F1, RMSE, and status.",
        {
            "job_id": {"type": "integer", "description": "Training job ID"},
        },
        required=["job_id"],
    ),
    _tool(
        "list_registered_models",
        "List all models in the registry with stage (staging/production), version, and metrics.",
        {},
    ),
    _tool(
        "compare_training_jobs",
        "Compare multiple training jobs side-by-side and identify the best by each metric.",
        {
            "job_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "List of training job IDs to compare",
            },
        },
        required=["job_ids"],
    ),
    _tool(
        "get_model_feature_importance",
        "Get feature importance scores for a registered model.",
        {
            "model_id": {"type": "integer", "description": "Registered model ID"},
        },
        required=["model_id"],
    ),
    # ── Monitoring (model performance) ──────────────────────────────────────────
    _tool(
        "get_model_performance",
        "Get live prediction stats for a deployed model: total predictions, latency, success rate.",
        {
            "model_id": {"type": "integer", "description": "Registered model ID"},
        },
        required=["model_id"],
    ),
    _tool(
        "get_model_drift",
        "Detect data drift for a deployed model using PSI/KS scores vs training baseline.",
        {
            "model_id": {"type": "integer", "description": "Registered model ID"},
        },
        required=["model_id"],
    ),
    _tool(
        "get_prediction_history",
        "Get recent prediction logs for a model.",
        {
            "model_id": {"type": "integer", "description": "Registered model ID"},
            "limit": {"type": "integer", "description": "Number of logs (default 20, max 100)"},
        },
        required=["model_id"],
    ),
]


class MLOpsToolExecutor:
    """Executes copilot tools against MLflow, Prometheus, and platform services."""

    async def execute(self, tool_name: str, arguments: Optional[Dict[str, Any]]) -> str:
        handler = getattr(self, f"_tool_{tool_name}", None)
        if not handler:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        # Groq (and other providers) may send None instead of {} for tools
        # that take no parameters — guard before unpacking with **.
        safe_args = arguments or {}
        try:
            result = await handler(**safe_args)
            return json.dumps(result, default=str)
        except Exception as exc:
            logger.warning("Tool %s failed: %s", tool_name, exc)
            return json.dumps({"error": str(exc), "tool": tool_name})

    async def _get_json(self, url: str, params: Optional[Dict] = None) -> Any:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def _post_json(self, url: str, body: Dict[str, Any]) -> Any:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=body)
            response.raise_for_status()
            return response.json()

    async def _find_model(self, model_id: int) -> Optional[Dict[str, Any]]:
        models = await self._get_json(f"{settings.TRAINING_SERVICE_URL}/models")
        if isinstance(models, list):
            for model in models:
                mid = model.get("id") if isinstance(model, dict) else getattr(model, "id", None)
                if mid == model_id:
                    if isinstance(model, dict):
                        return model
                    return {
                        "id": model.id,
                        "model_name": model.model_name,
                        "model_version": model.model_version,
                        "metadata_path": model.metadata_path,
                        "stage": model.stage,
                        "accuracy": model.accuracy,
                    }
        return None

    # ── MLflow ──────────────────────────────────────────────────────────────────

    async def _tool_mlflow_list_experiments(self) -> Dict[str, Any]:
        data = await self._post_json(
            f"{settings.MLFLOW_URL}/api/2.0/mlflow/experiments/search",
            {"max_results": 100},
        )
        experiments = data.get("experiments", [])
        return {
            "count": len(experiments),
            "experiments": [
                {
                    "experiment_id": e.get("experiment_id"),
                    "name": e.get("name"),
                    "lifecycle_stage": e.get("lifecycle_stage"),
                }
                for e in experiments
            ],
        }

    async def _tool_mlflow_search_runs(
        self,
        experiment_name: str = "training-service",
        max_results: int = 20,
    ) -> Dict[str, Any]:
        exp_data = await self._post_json(
            f"{settings.MLFLOW_URL}/api/2.0/mlflow/experiments/search",
            {"filter": f"name = '{experiment_name}'", "max_results": 1},
        )
        experiments = exp_data.get("experiments", [])
        if not experiments:
            return {"error": f"Experiment '{experiment_name}' not found", "runs": []}

        experiment_id = experiments[0]["experiment_id"]
        runs_data = await self._post_json(
            f"{settings.MLFLOW_URL}/api/2.0/mlflow/runs/search",
            {
                "experiment_ids": [experiment_id],
                "max_results": max_results,
                "order_by": ["attributes.start_time DESC"],
            },
        )

        runs = []
        for run in runs_data.get("runs", []):
            info = run.get("info", {})
            data = run.get("data", {})
            runs.append({
                "run_id": info.get("run_id"),
                "status": info.get("status"),
                "start_time": info.get("start_time"),
                "metrics": {m["key"]: m["value"] for m in data.get("metrics", [])},
                "params": {p["key"]: p["value"] for p in data.get("params", [])},
            })

        return {"experiment_name": experiment_name, "experiment_id": experiment_id, "runs": runs}

    async def _tool_mlflow_get_run(self, run_id: str) -> Dict[str, Any]:
        data = await self._get_json(
            f"{settings.MLFLOW_URL}/api/2.0/mlflow/runs/get",
            params={"run_id": run_id},
        )
        run = data.get("run", {})
        info = run.get("info", {})
        run_data = run.get("data", {})
        return {
            "run_id": info.get("run_id"),
            "status": info.get("status"),
            "experiment_id": info.get("experiment_id"),
            "start_time": info.get("start_time"),
            "end_time": info.get("end_time"),
            "metrics": {m["key"]: m["value"] for m in run_data.get("metrics", [])},
            "params": {p["key"]: p["value"] for p in run_data.get("params", [])},
        }

    # ── Prometheus ──────────────────────────────────────────────────────────────

    async def _tool_prometheus_query(self, query: str) -> Dict[str, Any]:
        data = await self._get_json(
            f"{settings.PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
        )
        return data

    async def _tool_prometheus_get_platform_metrics(self) -> Dict[str, Any]:
        overview = await self._get_json(
            f"{settings.MONITORING_SERVICE_URL}/system-overview"
        )

        prom_metrics: Dict[str, Any] = {}
        for metric_name in (
            "monitoring_requests_total",
            "system_cpu_usage_percent",
            "system_memory_usage_percent",
            "system_disk_usage_percent",
        ):
            try:
                result = await self._tool_prometheus_query(metric_name)
                prom_metrics[metric_name] = result.get("data", {}).get("result", [])
            except Exception as exc:
                prom_metrics[metric_name] = {"error": str(exc)}

        return {
            "system_overview": overview,
            "prometheus_metrics": prom_metrics,
        }

    # ── Deployment ──────────────────────────────────────────────────────────────

    async def _tool_list_deployments(self) -> Dict[str, Any]:
        deployments = await self._get_json(f"{settings.DEPLOYMENT_SERVICE_URL}/deployments")
        normalized = []
        if isinstance(deployments, list):
            for dep in deployments:
                if isinstance(dep, dict):
                    normalized.append(dep)
                else:
                    normalized.append({
                        "id": dep.id,
                        "model_id": dep.model_id,
                        "status": dep.status,
                        "endpoint": dep.endpoint,
                    })
        return {"count": len(normalized), "deployments": normalized}

    async def _tool_get_model_schema(self, model_id: int) -> Dict[str, Any]:
        return await self._get_json(
            f"{settings.DEPLOYMENT_SERVICE_URL}/predict/{model_id}/schema"
        )

    # ── Training ────────────────────────────────────────────────────────────────

    async def _tool_list_training_jobs(self, limit: int = 20) -> Dict[str, Any]:
        jobs = await self._get_json(f"{settings.TRAINING_SERVICE_URL}/training")
        if isinstance(jobs, list):
            return {"count": len(jobs[:limit]), "jobs": jobs[:limit]}
        return {"jobs": jobs}

    async def _tool_get_training_job(self, job_id: int) -> Dict[str, Any]:
        return await self._get_json(f"{settings.TRAINING_SERVICE_URL}/training/{job_id}")

    async def _tool_list_registered_models(self) -> Dict[str, Any]:
        models = await self._get_json(f"{settings.TRAINING_SERVICE_URL}/models")
        normalized = []
        if isinstance(models, list):
            for model in models:
                if isinstance(model, dict):
                    normalized.append(model)
                else:
                    normalized.append({
                        "id": model.id,
                        "model_name": model.model_name,
                        "model_version": model.model_version,
                        "stage": model.stage,
                        "accuracy": model.accuracy,
                        "training_job_id": model.training_job_id,
                        "metadata_path": model.metadata_path,
                    })
        return {"count": len(normalized), "models": normalized}

    async def _tool_compare_training_jobs(self, job_ids: List[int]) -> Dict[str, Any]:
        ids_param = ",".join(str(i) for i in job_ids)
        return await self._get_json(
            f"{settings.TRAINING_SERVICE_URL}/jobs/compare",
            params={"ids": ids_param},
        )

    async def _tool_get_model_feature_importance(self, model_id: int) -> Dict[str, Any]:
        return await self._get_json(
            f"{settings.TRAINING_SERVICE_URL}/models/{model_id}/feature-importance"
        )

    # ── Monitoring ──────────────────────────────────────────────────────────────

    async def _tool_get_model_performance(self, model_id: int) -> Dict[str, Any]:
        return await self._get_json(
            f"{settings.MONITORING_SERVICE_URL}/models/{model_id}/stats"
        )

    async def _tool_get_model_drift(self, model_id: int) -> Dict[str, Any]:
        model = await self._find_model(model_id)
        if not model:
            return {"error": f"Model {model_id} not found in registry"}
        metadata_path = model.get("metadata_path")
        if not metadata_path:
            return {"error": f"Model {model_id} has no metadata_path for drift baseline"}
        return await self._get_json(
            f"{settings.MONITORING_SERVICE_URL}/models/{model_id}/drift",
            params={"metadata_path": metadata_path},
        )

    async def _tool_get_prediction_history(
        self,
        model_id: int,
        limit: int = 20,
    ) -> Dict[str, Any]:
        limit = min(max(limit, 1), 100)
        logs = await self._get_json(
            f"{settings.MONITORING_SERVICE_URL}/models/{model_id}/history",
            params={"limit": limit},
        )
        return {"model_id": model_id, "count": len(logs) if isinstance(logs, list) else 0, "history": logs}


def parse_prometheus_text_metrics(text: str) -> Dict[str, float]:
    """Parse simple gauge/counter lines from Prometheus text exposition."""
    metrics: Dict[str, float] = {}
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        match = re.match(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)\s+([0-9.eE+-]+)", line)
        if match:
            metrics[match.group(1)] = float(match.group(2))
    return metrics


tool_executor = MLOpsToolExecutor()