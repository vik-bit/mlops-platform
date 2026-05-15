from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "deployment-service"
    ENVIRONMENT: str = "development"


settings = Settings()