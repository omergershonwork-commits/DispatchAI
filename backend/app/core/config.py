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
"""Base URL for the Qwen-compatible inference server."""

QWEN_MODEL_NAME = os.getenv("QWEN_MODEL_NAME", "qwen")
"""Model name sent to the Qwen-compatible inference server."""

QWEN_TIMEOUT_SECONDS = float(os.getenv("QWEN_TIMEOUT_SECONDS", "30"))
"""HTTP timeout in seconds for Qwen inference requests."""

QWEN_REQUEST_HEADERS_MODE = os.getenv("QWEN_REQUEST_HEADERS_MODE", "auto")
"""Header mode for Qwen requests: auto, none, or pinggy."""

QWEN_EXTRA_HEADERS_JSON = os.getenv("QWEN_EXTRA_HEADERS_JSON", "")
"""Optional JSON object of additional headers for Qwen requests."""

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
"""Telegram bot token used for sending replies. Must not be committed."""

TELEGRAM_API_BASE_URL = os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org")
"""Base URL for the Telegram Bot API."""

TELEGRAM_TIMEOUT_SECONDS = float(os.getenv("TELEGRAM_TIMEOUT_SECONDS", "10"))
"""HTTP timeout in seconds for Telegram Bot API requests."""


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings loaded from environment variables."""

    app_name: str = field(default=APP_NAME, metadata={"description": "FastAPI application name."})
    environment: str = field(default=ENVIRONMENT, metadata={"description": "Current runtime environment label."})
    database_url: str = field(default=DATABASE_URL, metadata={"description": "SQLAlchemy database connection URL."})
    qwen_base_url: str = field(default=QWEN_BASE_URL, metadata={"description": "Qwen-compatible inference server base URL."})
    qwen_model_name: str = field(default=QWEN_MODEL_NAME, metadata={"description": "Qwen model name used for generation."})
    qwen_timeout_seconds: float = field(default=QWEN_TIMEOUT_SECONDS, metadata={"description": "Qwen HTTP timeout in seconds."})
    qwen_request_headers_mode: str = field(
        default=QWEN_REQUEST_HEADERS_MODE,
        metadata={"description": "Qwen request header mode: auto, none, or pinggy."},
    )
    qwen_extra_headers_json: str = field(
        default=QWEN_EXTRA_HEADERS_JSON,
        metadata={"description": "Optional JSON object of extra Qwen request headers."},
    )
    telegram_bot_token: str = field(
        default=TELEGRAM_BOT_TOKEN,
        metadata={"description": "Telegram bot token used for sending replies."},
    )
    telegram_api_base_url: str = field(
        default=TELEGRAM_API_BASE_URL,
        metadata={"description": "Telegram Bot API base URL."},
    )
    telegram_timeout_seconds: float = field(
        default=TELEGRAM_TIMEOUT_SECONDS,
        metadata={"description": "Telegram Bot API timeout in seconds."},
    )


settings = Settings()
"""Shared settings instance imported by backend modules."""
