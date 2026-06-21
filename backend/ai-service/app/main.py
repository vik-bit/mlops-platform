from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routes.copilot import router as copilot_router
from app.core.config import settings
from app.services.tools import COPILOT_TOOLS
from app.services.http_client import get_client, close_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"AI Service starting — provider: {settings.LLM_PROVIDER}, model: {settings.LLM_MODEL}")
    print(f"Tool calling enabled with {len(COPILOT_TOOLS)} tools")
    await get_client()  # warm up shared httpx client (IPv4-only, tuned keepalive)
    yield
    await close_client()  # clean shutdown, no leaked sockets
    print("AI Service shutting down")


app = FastAPI(
    title="MLOps AI Service",
    description="MLOps Copilot — Groq-powered agent with MLflow, Prometheus, deployment, and training tools",
    version="2.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8000",
        "http://localhost:8001",
        "http://localhost:8002",
        "http://localhost:8003",
        "http://localhost:8004",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "https://mlops-frontend-5smr.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(copilot_router)


@app.get("/")
async def root():
    return {
        "service": "MLOps AI Service",
        "version": "2.3.0",
        "phase": "Phase 2.3 — MLOps Copilot with Tool Calling",
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "endpoints": {
            "chat": "/copilot/chat",
            "tools": "/copilot/tools",
            "explain_shap": "/copilot/explain-shap",
            "explain_drift": "/copilot/explain-drift",
            "compare_models": "/copilot/compare-models",
            "health": "/copilot/health",
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "ai-service"}