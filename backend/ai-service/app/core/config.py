from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    SERVICE_NAME: str = "ai-service"
    ENVIRONMENT: str = "development"

    # LLM Configuration — Groq is the default provider (OpenAI-compatible API)
    LLM_PROVIDER: str = "groq"
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_GROQ_URL: str = "https://api.groq.com/openai/v1"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 2048
    LLM_TIMEOUT: float = 120.0

    # Max messages to keep in context window before trimming oldest pairs
    LLM_MAX_CONTEXT_MESSAGES: int = 20

    # Max tool-calling iterations per chat turn
    LLM_MAX_TOOL_ITERATIONS: int = 6

    # Internal service URLs (Docker network uses port 8000)
    DEPLOYMENT_SERVICE_URL: str = "http://deployment-service:8000"
    MONITORING_SERVICE_URL: str = "http://monitoring-service:8000"
    TRAINING_SERVICE_URL: str = "http://training-service:8000"
    MLFLOW_URL: str = "http://mlflow:5000"
    PROMETHEUS_URL: str = "http://prometheus:9090"

    # Vector DB Configuration (for RAG - Phase 2.2)
    VECTOR_DB_URL: str = "http://vector-db:6333"
    VECTOR_DB_COLLECTION: str = "mlops_knowledge"

    class Config:
        env_file = ".env"


settings = Settings()
