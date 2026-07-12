import os
from dataclasses import dataclass, field

APP_NAME = os.getenv("APP_NAME", "ai-rescue-backend")
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/ai_rescue",
)

QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "http://localhost:8001")
QWEN_MODEL_NAME = os.getenv("QWEN_MODEL_NAME", "qwen")
QWEN_TIMEOUT_SECONDS = float(os.getenv("QWEN_TIMEOUT_SECONDS", "30"))
QWEN_REQUEST_HEADERS_MODE = os.getenv("QWEN_REQUEST_HEADERS_MODE", "auto")
QWEN_EXTRA_HEADERS_JSON = os.getenv("QWEN_EXTRA_HEADERS_JSON", "")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_INCIDENT_BOT_TOKEN = os.getenv("TELEGRAM_INCIDENT_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
TELEGRAM_VOLUNTEER_BOT_TOKEN = os.getenv("TELEGRAM_VOLUNTEER_BOT_TOKEN", "")
TELEGRAM_API_BASE_URL = os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org")
TELEGRAM_TIMEOUT_SECONDS = float(os.getenv("TELEGRAM_TIMEOUT_SECONDS", "10"))

GEOCODING_ENABLED = os.getenv("GEOCODING_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
GEOCODING_BASE_URL = os.getenv("GEOCODING_BASE_URL", "https://nominatim.openstreetmap.org")
GEOCODING_USER_AGENT = os.getenv("GEOCODING_USER_AGENT", "DispatchAI/1.0")
GEOCODING_TIMEOUT_SECONDS = float(os.getenv("GEOCODING_TIMEOUT_SECONDS", "8"))
GEOCODING_COUNTRY_CODES = os.getenv("GEOCODING_COUNTRY_CODES", "il")

DISPATCH_OFFER_TIMEOUT_SECONDS = int(os.getenv("DISPATCH_OFFER_TIMEOUT_SECONDS", "120"))
DISPATCH_TIMEOUT_POLL_SECONDS = int(os.getenv("DISPATCH_TIMEOUT_POLL_SECONDS", "15"))


@dataclass(frozen=True)
class Settings:
    app_name: str = field(default=APP_NAME)
    environment: str = field(default=ENVIRONMENT)
    log_level: str = field(default=LOG_LEVEL)
    database_url: str = field(default=DATABASE_URL)
    qwen_base_url: str = field(default=QWEN_BASE_URL)
    qwen_model_name: str = field(default=QWEN_MODEL_NAME)
    qwen_timeout_seconds: float = field(default=QWEN_TIMEOUT_SECONDS)
    qwen_request_headers_mode: str = field(default=QWEN_REQUEST_HEADERS_MODE)
    qwen_extra_headers_json: str = field(default=QWEN_EXTRA_HEADERS_JSON)
    telegram_bot_token: str = field(default=TELEGRAM_BOT_TOKEN)
    telegram_incident_bot_token: str = field(default=TELEGRAM_INCIDENT_BOT_TOKEN)
    telegram_volunteer_bot_token: str = field(default=TELEGRAM_VOLUNTEER_BOT_TOKEN)
    telegram_api_base_url: str = field(default=TELEGRAM_API_BASE_URL)
    telegram_timeout_seconds: float = field(default=TELEGRAM_TIMEOUT_SECONDS)
    geocoding_enabled: bool = field(default=GEOCODING_ENABLED)
    geocoding_base_url: str = field(default=GEOCODING_BASE_URL)
    geocoding_user_agent: str = field(default=GEOCODING_USER_AGENT)
    geocoding_timeout_seconds: float = field(default=GEOCODING_TIMEOUT_SECONDS)
    geocoding_country_codes: str = field(default=GEOCODING_COUNTRY_CODES)
    dispatch_offer_timeout_seconds: int = field(default=DISPATCH_OFFER_TIMEOUT_SECONDS)
    dispatch_timeout_poll_seconds: int = field(default=DISPATCH_TIMEOUT_POLL_SECONDS)


settings = Settings()
