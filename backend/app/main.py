from fastapi import FastAPI

from app.api.dispatch import router as dispatch_router
from app.api.health import router as health_router
from app.api.telegram import router as telegram_router
from app.api.volunteer_telegram import router as volunteer_telegram_router
from app.core.config import settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI backend application."""

    app = FastAPI(title=settings.app_name)
    app.include_router(health_router)
    app.include_router(telegram_router)
    app.include_router(volunteer_telegram_router)
    app.include_router(dispatch_router)
    return app


app = create_app()
"""ASGI application instance used by Uvicorn and tests."""
