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

QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "http://localhost:8001")
"""Base URL for the local Qwen-compatible inference server."""

QWEN_MODEL_NAME = os.getenv("QWEN_MODEL_NAME", "qwen")
"""Model name sent to the Qwen-compatible inference server."""

QWEN_TIMEOUT_SECONDS = float(os.getenv("QWEN_TIMEOUT_SECONDS", "30"))
"""HTTP timeout in seconds for Qwen inference requests."""


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings loaded from environment variables."""

    app_name: str = field(default=APP_NAME, metadata={"description": "FastAPI application name."})
    environment: str = field(default=ENVIRONMENT, metadata={"description": "Current runtime environment label."})
    database_url: str = field(default=DATABASE_URL, metadata={"description": "SQLAlchemy database connection URL."})
    qwen_base_url: str = field(default=QWEN_BASE_URL, metadata={"description": "Qwen-compatible inference server base URL."})
    qwen_model_name: str = field(default=QWEN_MODEL_NAME, metadata={"description": "Qwen model name used for generation."})
    qwen_timeout_seconds: float = field(default=QWEN_TIMEOUT_SECONDS, metadata={"description": "Qwen HTTP timeout in seconds."})


settings = Settings()
"""Shared settings instance imported by backend modules."""
