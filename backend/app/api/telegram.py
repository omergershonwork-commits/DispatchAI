from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

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
"""Safe response code returned when extraction fails after webhook acceptance."""

INCIDENT_PERSISTENCE_UNAVAILABLE_ERROR = "incident_persistence_unavailable"
"""Safe response code returned when incident persistence fails after webhook acceptance."""

TELEGRAM_REPLY_UNAVAILABLE_ERROR = "telegram_reply_unavailable"
"""Safe response code returned when Telegram reply sending fails after webhook acceptance."""

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
"""Router containing Telegram webhook ingestion endpoints."""


def get_incident_extraction_service() -> IncidentExtractionService:
    """Return the incident extraction service used by Telegram webhook ingestion."""

    return IncidentExtractionService()


def get_incident_persistence_service(db: Session = Depends(get_db)) -> IncidentPersistenceService:
    """Return the incident persistence service used by webhook ingestion."""

    return IncidentPersistenceService(db)


def get_telegram_bot_client() -> TelegramBotClient:
    """Return the Telegram Bot API client used for sending replies."""

    return TelegramBotClient()


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
    """Accept a Telegram webhook update, extract text details, persist it, and reply.

    This endpoint accepts the webhook regardless of extraction, persistence, or reply
    success so Telegram does not retry indefinitely. Volunteer dispatch is still out
    of scope for this endpoint.
    """

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
            extraction = extraction_service.extract_from_text(message.text)
        except (IncidentExtractionError, QwenClientError, ValueError):
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
    """Build a concise Telegram reply from extraction and persistence output."""

    if extraction_error or extraction is None:
        return (
            "I received your message, but I could not extract the incident details yet. "
            "Please send the location and what help is needed."
        )

    if not extraction.is_incident:
        return extraction.rejection_reason or (
            "I can only process incident reports right now. Please send what happened, "
            "where it happened, and what help is needed."
        )

    if persistence_error:
        return (
            "Incident report received, but I could not save it yet. "
            "Please resend the location and what help is needed in one message."
        )

    if extraction.should_ask_follow_up and extraction.follow_up_question:
        return extraction.follow_up_question

    if persistence_result:
        reply_lines = _build_persisted_reply_header(persistence_result)
    else:
        reply_lines = ["Incident report received."]

    if extraction.summary:
        reply_lines.append(f"Summary: {extraction.summary}")
    if extraction.location_text:
        reply_lines.append(f"Location: {extraction.location_text}")
    if extraction.urgency:
        reply_lines.append(f"Urgency: {extraction.urgency}")
    if extraction.needs:
        reply_lines.append(f"Needs: {', '.join(extraction.needs)}")

    if persistence_result and persistence_result.status == "ready_for_dispatch":
        reply_lines.append("This report is ready for dispatch matching.")
    else:
        reply_lines.append("I will keep tracking this report while dispatch support is being prepared.")

    return "\n".join(reply_lines)


def _build_persisted_reply_header(persistence_result: IncidentPersistenceResult) -> list[str]:
    """Return the first reply line for a persisted incident."""

    if persistence_result.updated:
        return [f"Incident #{persistence_result.incident_id} updated."]
    return [f"Incident #{persistence_result.incident_id} recorded."]
