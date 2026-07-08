import os
from dataclasses import dataclass

APP_NAME = os.getenv("APP_NAME", "ai-rescue-backend")
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/ai_rescue",
)


@dataclass(frozen=True)
class Settings:
    app_name: str = APP_NAME
    environment: str = ENVIRONMENT
    database_url: str = DATABASE_URL


settings = Settings()