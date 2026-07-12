import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api.dashboard import router as dashboard_router
from app.api.dispatch import router as dispatch_router
from app.api.health import router as health_router
from app.api.telegram import router as telegram_router
from app.api.volunteer_telegram import router as volunteer_telegram_router
from app.core.config import settings
from app.db.session import SessionLocal, ensure_database_schema, get_engine
from app.services.dispatch_lifecycle import DispatchLifecycleError, DispatchLifecycleService
from app.services.telegram_bot_client import TelegramBotClient

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def _run_dispatch_timeout_pass() -> None:
    if not settings.telegram_volunteer_bot_token.strip():
        logger.debug("dispatch_timeout_skipped reason=volunteer_bot_not_configured")
        return
    get_engine()
    db = SessionLocal()
    try:
        lifecycle = DispatchLifecycleService(
            db,
            volunteer_bot_client=TelegramBotClient(
                bot_token=settings.telegram_volunteer_bot_token
            ),
            incident_bot_client=(
                TelegramBotClient(bot_token=settings.telegram_incident_bot_token)
                if settings.telegram_incident_bot_token.strip()
                else None
            ),
            offer_timeout_seconds=settings.dispatch_offer_timeout_seconds,
        )
        expired = lifecycle.expire_unanswered_offers()
        if expired:
            logger.info("dispatch_timeout_pass expired_offers=%s", expired)
    except DispatchLifecycleError:
        logger.exception("dispatch_timeout_pass_failed")
    finally:
        db.close()


async def _dispatch_timeout_loop() -> None:
    logger.info(
        "dispatch_timeout_worker_started poll_seconds=%s offer_timeout_seconds=%s",
        settings.dispatch_timeout_poll_seconds,
        settings.dispatch_offer_timeout_seconds,
    )
    while True:
        await asyncio.sleep(settings.dispatch_timeout_poll_seconds)
        await asyncio.to_thread(_run_dispatch_timeout_pass)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "application_starting environment=%s geocoding_enabled=%s log_level=%s",
        settings.environment,
        settings.geocoding_enabled,
        settings.log_level,
    )
    await asyncio.to_thread(ensure_database_schema)
    logger.info("database_schema_ready")

    task: asyncio.Task | None = None
    if settings.dispatch_timeout_poll_seconds > 0:
        task = asyncio.create_task(_dispatch_timeout_loop())
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        logger.info("application_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(telegram_router)
    app.include_router(volunteer_telegram_router)
    app.include_router(dispatch_router)
    app.include_router(dashboard_router)
    return app


app = create_app()
