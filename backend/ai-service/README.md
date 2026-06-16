# MLOps AI Service - Phase 2.1: AI Copilot

## Overview

The AI Service is **Layer 2** of the MLOps platform. It adds LLM-powered intelligence on top of the existing Layer 1 MLOps infrastructure.

**Phase 2.1** implements the **AI Copilot** - an interactive assistant that:
- Explains SHAP values and feature importance in business-friendly language
- Analyzes and explains model drift and data drift
- Compares different model versions with recommendations
- Provides actionable insights about model behavior
- Maintains conversation context for multi-turn interactions

## Architecture

```
┌─────────────────────────────────────────────┐
│         Frontend (Chat UI)                  │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│         AI Service (Port 8005)              │
│  ┌──────────────────────────────────────┐  │
│  │  Chat & Conversation Management      │  │
│  │  ├─ SHAP Explainer                   │  │
│  │  ├─ Drift Analyzer                   │  │
│  │  ├─ Model Comparator                 │  │
│  │  └─ MLOps Data Fetcher               │  │
│  └──────────────────────────────────────┘  │
│           │                                  │
│           ▼                                  │
│  ┌──────────────────────────────────────┐  │
│  │   LLM Provider (OpenAI/Ollama/Gemini)│  │
│  └──────────────────────────────────────┘  │
└────────────────┬────────────────────────────┘
                 │
    ┌────────────┼────────────────┐
    │            │                │
    ▼            ▼                ▼
┌────────┐ ┌────────────┐ ┌──────────────┐
│Deployment│ │Monitoring │ │Training      │
│Service   │ │Service    │ │Service       │
└────────┘ └────────────┘ └──────────────┘
```

## Key Components

### 1. **LLMService** (`services/llm.py`)
Handles communication with different LLM providers:
- **OpenAI**: Uses GPT-4 (configurable model)
- **Ollama**: Local LLM option for privacy/cost
- **Google Gemini**: Alternative cloud option

**Configuration via environment variables:**
```
LLM_PROVIDER=openai|ollama|gemini
LLM_API_KEY=<your-api-key>
LLM_MODEL=gpt-4|gpt-3.5-turbo|gemini-pro|neural-chat|etc
```

### 2. **MLOpsCopilot** (`services/copilot.py`)
Main orchestrator combining all AI capabilities:
- **SHAPExplainer**: Converts SHAP values to natural language
- **DriftAnalyzer**: Explains data/model drift with severity and recommendations
- **ModelComparator**: Analyzes model versions and recommends best option
- **MLOpsDataFetcher**: Retrieves data from monitoring, deployment, and training services

### 3. **API Routes** (`routes/copilot.py`)
REST endpoints for client integration:
- `POST /api/copilot/chat` - General conversation
- `POST /api/copilot/explain-shap` - Explain SHAP values
- `POST /api/copilot/explain-drift` - Explain model drift
- `POST /api/copilot/compare-models` - Compare model versions
- `GET /api/copilot/context` - View conversation history
- `POST /api/copilot/reset-context` - Clear conversation
- `GET /api/copilot/health` - Health check

## Setup & Installation

### 1. Prerequisites
- Python 3.11+
- Docker & Docker Compose (optional)
- LLM API key (OpenAI, Gemini, or local Ollama)

### 2. Local Development

```bash
cd backend/ai-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure LLM
cp .env.example .env
# Edit .env and add your LLM_API_KEY and provider settings

# Run the service
python -m uvicorn app.main:app --reload --port 8005
```

### 3. Docker Deployment

```bash
# From project root
docker-compose up ai-service

# The service will be available at http://localhost:8005
```

### 4. Configuration

Create `.env` file in `backend/ai-service/`:

```
# Required: Choose your LLM provider
LLM_PROVIDER=openai  # or: ollama, gemini

# For OpenAI
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4

# For Ollama (local - no API key needed)
# LLM_PROVIDER=ollama
# LLM_MODEL=neural-chat

# For Google Gemini
# LLM_PROVIDER=gemini
# LLM_API_KEY=AIza...
# LLM_MODEL=gemini-pro

# Service interconnect (default values shown)
DEPLOYMENT_SERVICE_URL=http://deployment-service:8003
MONITORING_SERVICE_URL=http://monitoring-service:8004
TRAINING_SERVICE_URL=http://training-service:8002
```

## Usage Examples

### 1. Chat with Copilot

```bash
curl -X POST http://localhost:8005/api/copilot/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Why did my model accuracy drop?"}'
```

Response:
```json
{
  "response": "I found that your model accuracy dropped due to... [detailed analysis]",
  "context_length": 2
}
```

### 2. Explain SHAP Values

```bash
curl -X POST http://localhost:8005/api/copilot/explain-shap \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "housing_model",
    "shap_data": {
      "base_value": 150000,
      "values": {
        "median_income": 45000,
        "latitude": 25000,
        "longitude": -15000,
        "population": -5000
      }
    }
  }'
```

### 3. Explain Model Drift

```bash
curl -X POST http://localhost:8005/api/copilot/explain-drift \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "housing_model",
    "drift_data": {
      "drift_score": 0.23,
      "drifted_features": ["latitude", "population"],
      "severity": "medium"
    }
  }'
```

### 4. Compare Models

```bash
curl -X POST http://localhost:8005/api/copilot/compare-models \
  -H "Content-Type: application/json" \
  -d '{
    "models": [
      {"name": "v1", "accuracy": 0.87, "latency_ms": 45},
      {"name": "v2", "accuracy": 0.89, "latency_ms": 52},
      {"name": "v3", "accuracy": 0.88, "latency_ms": 40}
    ],
    "question": "Which version should we deploy?"
  }'
```

## LLM Provider Comparison

| Provider | Cost | Speed | Quality | Privacy | Setup |
|----------|------|-------|---------|---------|-------|
| **OpenAI** | $$$ | Fast | Excellent | Cloud | API Key |
| **Ollama** | Free | Slow | Good | Local | Docker |
| **Gemini** | $$ | Fast | Excellent | Cloud | API Key |

### Recommendation
- **Production**: OpenAI GPT-4 (best quality)
- **Development**: Ollama (free, local)
- **Cost-sensitive**: Gemini or local Ollama

## Phase 2.1 Capabilities

✅ **Implemented:**
- Chat interface with conversation context
- SHAP value explanation
- Model drift analysis
- Model version comparison
- Integration with Layer 1 services
- Multiple LLM provider support

## Phase 2.2: RAG Layer (Coming Next)

After Phase 2.1, we'll add:
- Vector database for model metadata
- Training logs and monitoring reports storage
- SHAP analysis history
- Semantic search over MLOps knowledge base

**Example queries:**
- "Which model had the highest accuracy?"
- "Why was model v5 retrained?"
- "Show drift history of the housing model"

## Phase 2.3: Autonomous Agent (Coming Later)

Final layer adds:
- Tool calling to trigger training
- Automatic drift detection and retraining
- Deployment automation
- Multi-step problem solving

**Example automation:**
1. User: "My model performance is degrading"
2. Agent checks monitoring service
3. Detects drift
4. Starts retraining automatically
5. Evaluates new model
6. Deploys if better
7. Sends report

## Troubleshooting

### LLM API Connection Issues

```
Error: "Could not connect to LLM provider"
```

**Solutions:**
1. Check LLM_API_KEY is set correctly
2. Verify LLM_PROVIDER value
3. Test API key directly: `curl https://api.openai.com/v1/models -H "Authorization: Bearer $LLM_API_KEY"`
4. Check network connectivity to LLM provider

### Service Discovery Issues

```
Error: "Could not fetch drift data"
```

**Solutions:**
1. Verify other services are running: `docker-compose ps`
2. Check service URLs in `.env`
3. Test service connectivity: `curl http://monitoring-service:8004/health`
4. Check Docker network: `docker network inspect mlops_network`

## Testing

```bash
# Health check
curl http://localhost:8005/health

# Simple chat
curl -X POST http://localhost:8005/api/copilot/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, how can you help?"}'
```

## Performance Notes

- Conversation context grows with each message (no automatic cleanup)
- Use `POST /api/copilot/reset-context` to clear history
- LLM response time: 1-5s depending on provider
- Drift analysis requires monitoring service to be available

## Next Steps

1. **Build Frontend**: Create chat UI in Next.js/React
2. **Integrate with Gateway**: Add AI service to API Gateway routing
3. **Implement Phase 2.2**: Add vector DB and RAG capabilities
4. **Monitor Performance**: Track LLM costs and response times

---

**Built on**: FastAPI, Python 3.11, LLM APIs
**Port**: 8005
**Status**: Phase 2.1 - Production Ready
