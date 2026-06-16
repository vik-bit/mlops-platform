from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routes.copilot import router as copilot_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifecycle."""
    print(f"AI Service starting with LLM provider: {settings.LLM_PROVIDER}")
    print(f"Model: {settings.LLM_MODEL}")
    yield
    print("AI Service shutting down")


app = FastAPI(
    title="MLOps AI Service",
    description="AI/LLM layer for MLOps platform - AI Copilot for explaining models, drift, and comparisons",
    version="2.1.0",
    lifespan=lifespan
)

# CORS configuration
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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(copilot_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "MLOps AI Service",
        "version": "2.1.0",
        "phase": "Phase 2.1 - AI Copilot",
        "llm_provider": settings.LLM_PROVIDER,
        "endpoints": {
            "chat": "/api/copilot/chat",
            "explain_shap": "/api/copilot/explain-shap",
            "explain_drift": "/api/copilot/explain-drift",
            "compare_models": "/api/copilot/compare-models",
            "health": "/api/copilot/health"
        }
    }


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "healthy",
        "service": "ai-service"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8005,
        reload=True
    )
