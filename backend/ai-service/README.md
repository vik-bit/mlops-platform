# MLOps AI Service — MLOps Copilot with Tool Calling

## Overview

The AI Service adds a **Groq-powered MLOps Copilot** on top of the platform. It uses **function/tool calling** to query live data from MLflow, Prometheus, deployment-service, and training-service, then synthesizes natural-language answers.

**Capabilities:**
- Answer questions about **MLflow experiments and training runs**
- Query **Prometheus metrics** (CPU, memory, request counts, custom PromQL)
- Inspect **deployments** and model input schemas
- Compare **training jobs** and registered models
- Report **model performance**, drift, and prediction history
- Explain SHAP values, drift reports, and model comparisons (specialized panels)

## Architecture

```
User question
     │
     ▼
MLOpsCopilot (agent loop)
     │
     ├── Groq LLM (llama-3.3-70b-versatile)
     │     └── decides which tools to call
     │
     └── Tool Executor
           ├── MLflow API
           ├── Prometheus API
           ├── deployment-service
           ├── training-service
           └── monitoring-service
```

## Tools (15 total)

| Tool | Source | Purpose |
|------|--------|---------|
| `mlflow_list_experiments` | MLflow | List experiments |
| `mlflow_search_runs` | MLflow | Search runs with metrics/params |
| `mlflow_get_run` | MLflow | Run details by ID |
| `prometheus_query` | Prometheus | Run PromQL queries |
| `prometheus_get_platform_metrics` | Prometheus + Monitoring | Platform health & metrics |
| `list_deployments` | Deployment | Active deployments |
| `get_model_schema` | Deployment | Feature schema for a model |
| `list_training_jobs` | Training | All training jobs |
| `get_training_job` | Training | Job details by ID |
| `list_registered_models` | Training | Model registry |
| `compare_training_jobs` | Training | Side-by-side job comparison |
| `get_model_feature_importance` | Training | Feature importance |
| `get_model_performance` | Monitoring | Prediction stats |
| `get_model_drift` | Monitoring | PSI/KS drift detection |
| `get_prediction_history` | Monitoring | Recent prediction logs |

## Setup

### 1. Get a Groq API key

Sign up at [console.groq.com](https://console.groq.com) and create an API key.

### 2. Configure environment

```bash
cd backend/ai-service
cp .env.example .env
# Edit .env and set LLM_API_KEY=gsk_...
```

Or set `GROQ_API_KEY` in the project root for Docker Compose:

```bash
export GROQ_API_KEY=gsk_your_key_here
docker-compose up ai-service
```

### 3. Run locally

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8005
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/copilot/chat` | Agent chat with tool calling |
| `GET` | `/copilot/tools` | List available tools |
| `POST` | `/copilot/tools/invoke` | Directly invoke a tool |
| `POST` | `/copilot/explain-shap` | SHAP explanation |
| `POST` | `/copilot/explain-drift` | Drift analysis |
| `POST` | `/copilot/compare-models` | Model comparison |
| `GET` | `/copilot/health` | Health + provider info |

Via API Gateway: `/api/copilot/*`

## Example Queries

The copilot automatically selects tools based on your question:

```
"What MLflow experiments do we have?"
"Show me the latest training runs and their accuracy"
"Which models are deployed in production?"
"Compare training jobs 1, 2, and 3"
"What is the CPU usage on the platform?"
"Is model 1 experiencing data drift?"
"What's the prediction success rate for model 2?"
```

### Chat API

```bash
curl -X POST http://localhost:8005/copilot/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "List all deployed models and their endpoints"}'
```

Response:
```json
{
  "response": "There are 2 active deployments...",
  "context_length": 2,
  "tools_used": ["list_deployments", "list_registered_models"]
}
```

### List Tools

```bash
curl http://localhost:8005/copilot/tools
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `groq` | `groq`, `openai`, or `gemini` |
| `LLM_API_KEY` | — | Groq/OpenAI/Gemini API key |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Model name |
| `LLM_MAX_TOOL_ITERATIONS` | `6` | Max tool-call rounds per chat turn |
| `MLFLOW_URL` | `http://mlflow:5000` | MLflow tracking server |
| `PROMETHEUS_URL` | `http://prometheus:9090` | Prometheus server |
| `DEPLOYMENT_SERVICE_URL` | `http://deployment-service:8000` | Internal URL |
| `TRAINING_SERVICE_URL` | `http://training-service:8000` | Internal URL |
| `MONITORING_SERVICE_URL` | `http://monitoring-service:8000` | Internal URL |

## LLM Providers

| Provider | Tool Calling | Notes |
|----------|-------------|-------|
| **Groq** (default) | Yes | Fast, free tier available |
| **OpenAI** | Yes | Set `LLM_PROVIDER=openai` |
| **Gemini** | No | Falls back to chat without tools |

---

**Built on:** FastAPI, Groq API, httpx  
**Port:** 8005  
**Status:** Phase 2.3 — Tool Calling Copilot
