# MLOps Platform

A self-hosted machine learning operations platform that runs the full model lifecycle—dataset upload, training, registry, deployment, and monitoring—from a single web console. Version 1 delivers a working end-to-end pipeline with AI-assisted operations and containerized deployment infrastructure.

---

## What This Project Does

Most ML work stalls between a trained notebook and something others can actually use. This platform closes that gap by wiring each stage into one system:

| Stage | What happens |
|-------|--------------|
| **Datasets** | Upload CSV files, inspect column profiles, pick a target column |
| **Training** | Queue jobs on scikit-learn / XGBoost / LightGBM with logged metrics in MLflow |
| **Registry** | Persist trained models with version metadata |
| **Deployment** | Expose models as HTTP endpoints with inline prediction and SHAP explanation |
| **Monitoring** | Track prediction volume, latency, drift (PSI/KS), and request history |
| **AI Copilot** | Ask natural-language questions; the agent queries live platform data via tool calling |

---

## Decisions Made (v1)

These choices shaped the current architecture:

- **Microservices over monolith** — Dataset, training, deployment, monitoring, and AI services run independently behind an API Gateway. Each service owns one lifecycle stage and can be restarted or scaled without taking down the rest.
- **Docker Compose for local and demo deployments** — All services, PostgreSQL, Redis, MLflow, and Prometheus start with one command. Kubernetes manifests are planned for v2-scale deployments.
- **Async training via Redis** — Training jobs are queued rather than blocking HTTP requests, so the UI stays responsive while long-running jobs execute.
- **MLflow for experiment tracking** — Every training run logs parameters, metrics, and artifacts to a dedicated MLflow server (port 5000).
- **Groq LLM with tool calling for the Copilot** — Instead of a static chatbot, the AI service calls 15 platform APIs (MLflow, Prometheus, training, deployment, monitoring) to answer from live data.
- **JWT auth at the gateway** — All API routes pass through the gateway, which validates tokens before proxying to downstream services.

---

## Constraints Faced

- **Single-node deployment** — v1 targets one machine running Docker Compose, not a multi-tenant cluster.
- **Tabular ML only** — Training supports CSV datasets and classical / gradient-boosted models; deep learning and image pipelines are out of scope for v1.
- **Basic auth** — JWT login with admin/user roles. Enterprise SSO, OAuth, and fine-grained RBAC are deferred to v2.
- **Copilot requires an external LLM key** — The AI service needs a Groq API key (free tier available) to function.

---

## Outcomes Achieved (v1)

- End-to-end flow works: upload → train → deploy → predict → monitor
- Training metrics visible in both the UI and MLflow
- Deployed models serve predictions with latency tracking and SHAP explanations
- Drift detection (PSI/KS) runs against live prediction history
- Prometheus scrapes platform metrics; the Copilot can query them with PromQL
- Next.js dashboard connects to all backend services through the gateway

---

## Architecture

```
Browser (Next.js Dashboard)
         │
         ▼
   API Gateway :8000  ─── JWT auth, request routing
         │
    ┌────┼────────────┬──────────────┬─────────────┐
    ▼    ▼            ▼              ▼             ▼
Dataset Training  Deployment  Monitoring    AI Service
 :8001    :8002       :8003        :8004         :8005
    │       │            │              │             │
    └───────┴────────────┴──────────────┴─────────────┘
                         │
              PostgreSQL · Redis · MLflow · Prometheus
```

### Services

| Service | Port | Responsibility |
|---------|------|----------------|
| API Gateway | 8000 | Auth, routing, CORS |
| Dataset Service | 8001 | Upload, storage, profiling |
| Training Service | 8002 | Job queue, model training, registry |
| Deployment Service | 8003 | Model loading, inference, SHAP |
| Monitoring Service | 8004 | Prediction logging, drift, stats |
| AI Service | 8005 | LLM Copilot with tool calling |
| MLflow | 5000 | Experiment tracking UI |
| Prometheus | 9090 | Metrics collection |
| PostgreSQL | 5433 | Metadata and user store |
| Redis | 6379 | Training job queue |

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ and pnpm (for the frontend)
- A [Groq API key](https://console.groq.com) (for the AI Copilot)

### 1. Clone and configure

```bash
git clone <repository-url>
cd MLOPS_Platform
```

Create a `.env` file in the project root:

```env
GROQ_API_KEY=gsk_your_key_here
```

The AI service reads this key at startup. See `backend/ai-service/.env.example` for additional LLM settings.

### 2. Start backend services

```bash
docker compose up --build
```

Wait until all containers are healthy. The API Gateway is available at `http://localhost:8000`.

On first boot, the gateway seeds a default admin account:

| Username | Password |
|----------|----------|
| `admin`  | `admin123` |

Change this password before any production use.

### 3. Start the frontend

```bash
cd frontend/vertex-ai-frontend
pnpm install
```

Create `frontend/vertex-ai-frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_POLLING_INTERVAL=5000
```

```bash
pnpm dev
```

Open `http://localhost:3000` and sign in with the admin credentials.

### 4. Verify the stack

| Check | URL |
|-------|-----|
| Gateway health | `http://localhost:8000/health` |
| MLflow UI | `http://localhost:5000` |
| Prometheus | `http://localhost:9090` |
| Copilot health | `http://localhost:8005/copilot/health` |

---

## Version Roadmap

### v1 — Current (Pipeline, AI, Deployment Infra)

Focus: make the core ML lifecycle work reliably in a containerized environment.

- Dataset upload and profiling
- Async training with 8 model types and MLflow logging
- Model registry and deployment to HTTP endpoints
- Prediction, batch inference, and SHAP explanations
- Monitoring: stats, prediction history, drift detection
- AI Copilot with 15 live-data tools (Groq LLM)
- Docker Compose orchestration with PostgreSQL, Redis, Prometheus

### v2 — Planned

Focus: richer analytics, knowledge retrieval, and production-grade infrastructure.

| Area | Planned work |
|------|-------------|
| **Visualization** | Interactive training curves, feature charts, deployment dashboards |
| **Feature engineering** | Built-in transforms, feature store integration, pipeline templates |
| **RAG** | Vector database-backed knowledge retrieval for the Copilot |
| **Scalable infra** | Redis caching layer, full auth/SSO, message queues for async workflows, Kubernetes deployment |

---

## Repository Structure

```
MLOPS_Platform/
├── backend/
│   ├── api-gateway/        # Auth, routing, proxy
│   ├── dataset-service/    # Upload and profiling
│   ├── training-service/   # Training jobs and registry
│   ├── deployment-service/ # Model serving
│   ├── monitoring-service/ # Drift and prediction logs
│   └── ai-service/         # LLM Copilot
├── frontend/
│   └── vertex-ai-frontend/ # Next.js dashboard
├── shared/                 # Database models, schemas, contracts
├── docs/                   # Architecture and design documents
├── datasets/               # Uploaded dataset storage (runtime)
├── saved_models/           # Trained model artifacts (runtime)
└── docker-compose.yml
```

---

## Documentation

| Document | Contents |
|----------|----------|
| [Frontend README](frontend/vertex-ai-frontend/README.md) | Dashboard setup; in-app guide at **How to Use** in the sidebar |
| [AI Service README](backend/ai-service/README.md) | Copilot configuration and API reference |
| [docs/deployment.md](docs/deployment.md) | Infrastructure and deployment architecture |
| [docs/roadmap.md](docs/roadmap.md) | Full implementation roadmap |
| [docs/observability.md](docs/observability.md) | Monitoring and metrics design |

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Frontend | Next.js 16, React 19, Tailwind CSS, Recharts |
| Backend | FastAPI, SQLAlchemy, Celery, scikit-learn, XGBoost, LightGBM |
| Data | PostgreSQL, Redis, MLflow |
| Observability | Prometheus, custom monitoring service |
| AI | Groq LLM (llama-3.3-70b-versatile) with function calling |
| Infrastructure | Docker, Docker Compose |

---

## License

MIT
