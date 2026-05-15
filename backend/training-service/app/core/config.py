from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "training-service"
    ENVIRONMENT: str = "development"


settings = Settings()