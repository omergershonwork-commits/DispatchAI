from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.incident import IncidentExtractionResult
from app.schemas.telegram import TelegramWebhookAccepted, TelegramWebhookUpdate
from app.services.incident_extraction import IncidentExtractionError, IncidentExtractionService
from app.services.incident_persistence import (
    IncidentPersistenceError,
    IncidentPersistenceResult,
    IncidentPersistenceService,
    SourceIncidentContext,
)
from app.services.qwen_client import QwenClientError
from app.services.telegram_bot_client import TelegramBotClient, TelegramBotClientError

EXTRACTION_UNAVAILABLE_ERROR = "incident_extraction_unavailable"
INCIDENT_PERSISTENCE_UNAVAILABLE_ERROR = "incident_persistence_unavailable"
TELEGRAM_REPLY_UNAVAILABLE_ERROR = "telegram_reply_unavailable"

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_incident_extraction_service() -> IncidentExtractionService:
    """Return the incident extraction service used by Telegram webhook ingestion."""

    return IncidentExtractionService()


def get_incident_persistence_service(db: Session = Depends(get_db)) -> IncidentPersistenceService:
    """Return the incident persistence service used by webhook ingestion."""

    return IncidentPersistenceService(db)


def get_telegram_bot_client() -> TelegramBotClient:
    """Return the Telegram Bot API client used for incident bot replies."""

    return TelegramBotClient(bot_token=settings.telegram_incident_bot_token)


@router.post(
    "/telegram",
    response_model=TelegramWebhookAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def receive_telegram_webhook(
    update: TelegramWebhookUpdate,
    extraction_service: IncidentExtractionService = Depends(get_incident_extraction_service),
    incident_persistence_service: IncidentPersistenceService = Depends(get_incident_persistence_service),
    telegram_bot_client: TelegramBotClient = Depends(get_telegram_bot_client),
) -> TelegramWebhookAccepted:
    """Accept an incident Telegram update, preserve context, persist it, and reply."""

    message = update.message
    extraction: IncidentExtractionResult | None = None
    extraction_error: str | None = None
    persistence_result: IncidentPersistenceResult | None = None
    persistence_error: str | None = None
    telegram_reply_sent = False
    telegram_reply_error: str | None = None

    if message and message.text and message.text.strip():
        source_context = build_telegram_source_context(update)
        try:
            context_builder = getattr(incident_persistence_service, "build_extraction_text", None)
            extraction_text = (
                context_builder(source_context)
                if callable(context_builder)
                else source_context.raw_text
            )
            extraction = extraction_service.extract_from_text(extraction_text)
        except (IncidentExtractionError, IncidentPersistenceError, QwenClientError, ValueError):
            extraction_error = EXTRACTION_UNAVAILABLE_ERROR

        if extraction is not None:
            try:
                persistence_result = incident_persistence_service.persist_incident(
                    source_context,
                    extraction,
                )
            except (IncidentPersistenceError, ValueError):
                persistence_error = INCIDENT_PERSISTENCE_UNAVAILABLE_ERROR

        reply_text = build_telegram_reply_text(
            extraction,
            extraction_error,
            persistence_result,
            persistence_error,
        )
        try:
            telegram_bot_client.send_message(message.chat.id, reply_text)
            telegram_reply_sent = True
        except (TelegramBotClientError, ValueError):
            telegram_reply_error = TELEGRAM_REPLY_UNAVAILABLE_ERROR

    return TelegramWebhookAccepted(
        update_id=update.update_id,
        message_id=message.message_id if message else None,
        chat_id=message.chat.id if message else None,
        has_text=bool(message and message.text),
        extraction=extraction,
        extraction_error=extraction_error,
        incident_id=persistence_result.incident_id if persistence_result else None,
        incident_created=persistence_result.created if persistence_result else False,
        incident_status=persistence_result.status if persistence_result else None,
        persistence_error=persistence_error,
        telegram_reply_sent=telegram_reply_sent,
        telegram_reply_error=telegram_reply_error,
    )


def build_telegram_source_context(update: TelegramWebhookUpdate) -> SourceIncidentContext:
    """Translate a Telegram webhook update into generic incident source metadata."""

    message = update.message
    if message is None or message.text is None:
        raise ValueError("Telegram text message is required to build source context.")

    return SourceIncidentContext(
        source="telegram",
        source_update_id=update.update_id,
        source_message_id=message.message_id,
        source_chat_id=message.chat.id,
        raw_text=message.text,
    )


def build_telegram_reply_text(
    extraction: IncidentExtractionResult | None,
    extraction_error: str | None,
    persistence_result: IncidentPersistenceResult | None = None,
    persistence_error: str | None = None,
) -> str:
    """Build a calm user-facing reply without exposing backend workflow details."""

    if extraction_error or extraction is None:
        return (
            "I received your message, but I still need clearer details. "
            "Please send what happened, your exact location, and the help you need. "
            "If there is immediate danger, contact local emergency services now."
        )

    if not extraction.is_incident:
        return extraction.rejection_reason or (
            "Please describe what happened, the exact location, and the help that is needed."
        )

    if persistence_error:
        return (
            "I understood your report, but I could not save it. "
            "Please resend the full report in one message. "
            "If there is immediate danger, contact local emergency services now."
        )

    if extraction.should_ask_follow_up and extraction.follow_up_question:
        return (
            "Your report has been received. I need one more detail before it can be matched.\n"
            f"{extraction.follow_up_question}\n"
            "If there is immediate danger, contact local emergency services now."
        )

    if persistence_result and persistence_result.status == "ready_for_dispatch":
        return (
            "Your emergency report has been received and saved. "
            "Available volunteers are now being matched. "
            "A responder has not yet been confirmed. "
            "If there is immediate danger, contact local emergency services now."
        )

    return (
        "Your report has been received. Please remain available in this chat for follow-up questions. "
        "If there is immediate danger, contact local emergency services now."
    )
