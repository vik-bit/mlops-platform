from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    SERVICE_NAME: str = "ai-service"
    ENVIRONMENT: str = "development"

    # LLM Configuration
    # Default to ollama — matches the UI label "Connected to Ollama • neural-chat"
    # Set LLM_PROVIDER=openai + LLM_API_KEY in .env to switch to OpenAI
    LLM_PROVIDER: str = "ollama"
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "neural-chat"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000
    LLM_TIMEOUT: float = 400.0

    # Ollama Configuration
    LLM_OLLAMA_URL: str = "http://ollama:11434"

    # Max messages to keep in context window before trimming oldest pairs
    LLM_MAX_CONTEXT_MESSAGES: int = 20

    # Service URLs
    DEPLOYMENT_SERVICE_URL: str = "http://deployment-service:8000"
    MONITORING_SERVICE_URL: str = "http://monitoring-service:8000"
    TRAINING_SERVICE_URL: str = "http://training-service:8000"

    # Vector DB Configuration (for RAG - Phase 2.2)
    VECTOR_DB_URL: str = "http://vector-db:6333"
    VECTOR_DB_COLLECTION: str = "mlops_knowledge"

    class Config:
        env_file = ".env"


settings = Settings()