from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "api-gateway"
    ENVIRONMENT: str = "development"


settings = Settings()