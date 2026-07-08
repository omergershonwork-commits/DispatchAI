import os
from dataclasses import dataclass, field

APP_NAME = os.getenv("APP_NAME", "ai-rescue-backend")
"""Backend application name used by FastAPI metadata."""

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
"""Runtime environment label used for local, test, or deployed environments."""

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/ai_rescue",
)
"""SQLAlchemy database URL for the PostgreSQL/PostGIS database."""


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings loaded from environment variables."""

    app_name: str = field(default=APP_NAME, metadata={"description": "FastAPI application name."})
    environment: str = field(default=ENVIRONMENT, metadata={"description": "Current runtime environment label."})
    database_url: str = field(default=DATABASE_URL, metadata={"description": "SQLAlchemy database connection URL."})


settings = Settings()
"""Shared settings instance imported by backend modules."""
