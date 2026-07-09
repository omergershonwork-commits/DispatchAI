from fastapi import APIRouter, Depends, status

from app.schemas.incident import IncidentExtractionResult
from app.schemas.telegram import TelegramWebhookAccepted, TelegramWebhookUpdate
from app.services.incident_extraction import IncidentExtractionError, IncidentExtractionService
from app.services.qwen_client import QwenClientError

EXTRACTION_UNAVAILABLE_ERROR = "incident_extraction_unavailable"
"""Safe response code returned when extraction fails after webhook acceptance."""

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
"""Router containing Telegram webhook ingestion endpoints."""


def get_incident_extraction_service() -> IncidentExtractionService:
    """Return the incident extraction service used by Telegram webhook ingestion."""

    return IncidentExtractionService()


@router.post(
    "/telegram",
    response_model=TelegramWebhookAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def receive_telegram_webhook(
    update: TelegramWebhookUpdate,
    extraction_service: IncidentExtractionService = Depends(get_incident_extraction_service),
) -> TelegramWebhookAccepted:
    """Accept a Telegram webhook update and run extraction for text messages.

    This endpoint accepts the webhook regardless of extraction success so Telegram
    does not retry indefinitely. It does not send Telegram replies, persist
    incidents, or dispatch volunteers yet.
    """

    # Telegram message payload when this update includes a message.
    message = update.message

    extraction: IncidentExtractionResult | None = None
    """Incident extraction result for Telegram text messages."""

    extraction_error: str | None = None
    """Safe extraction error code when extraction fails after webhook acceptance."""

    if message and message.text and message.text.strip():
        try:
            extraction = extraction_service.extract_from_text(message.text)
        except (IncidentExtractionError, QwenClientError, ValueError):
            extraction_error = EXTRACTION_UNAVAILABLE_ERROR

    return TelegramWebhookAccepted(
        update_id=update.update_id,
        message_id=message.message_id if message else None,
        chat_id=message.chat.id if message else None,
        has_text=bool(message and message.text),
        extraction=extraction,
        extraction_error=extraction_error,
    )
