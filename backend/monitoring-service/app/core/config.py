from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "monitoring-service"
    ENVIRONMENT: str = "development"


settings = Settings()