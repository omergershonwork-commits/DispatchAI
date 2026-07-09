from typing import Protocol

from fastapi import APIRouter, Depends, status

from app.schemas.incident import IncidentExtractionResult
from app.schemas.telegram import TelegramWebhookAccepted, TelegramWebhookUpdate
from app.services.incident_extraction import IncidentExtractionError, IncidentExtractionService
from app.services.qwen_client import QwenClientError
from app.services.telegram_bot_client import TelegramBotClient, TelegramBotClientError

EXTRACTION_UNAVAILABLE_ERROR = "incident_extraction_unavailable"
"""Safe response code returned when extraction fails after webhook acceptance."""

TELEGRAM_REPLY_UNAVAILABLE_ERROR = "telegram_reply_unavailable"
"""Safe response code returned when Telegram reply sending fails after webhook acceptance."""

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
"""Router containing Telegram webhook ingestion endpoints."""


class TelegramReplySender(Protocol):
    """Protocol for objects that can send Telegram chat replies."""

    def send_message(self, chat_id: int, text: str) -> object:
        """Send a text message to a Telegram chat."""


def get_incident_extraction_service() -> IncidentExtractionService:
    """Return the incident extraction service used by Telegram webhook ingestion."""

    return IncidentExtractionService()


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
    telegram_bot_client: TelegramReplySender = Depends(get_telegram_bot_client),
) -> TelegramWebhookAccepted:
    """Accept a Telegram webhook update, extract text details, and reply to the chat.

    This endpoint accepts the webhook regardless of extraction or reply success so
    Telegram does not retry indefinitely. It does not persist incidents or dispatch
    volunteers yet.
    """

    message = update.message

    extraction: IncidentExtractionResult | None = None
    extraction_error: str | None = None
    telegram_reply_sent = False
    telegram_reply_error: str | None = None

    if message and message.text and message.text.strip():
        try:
            extraction = extraction_service.extract_from_text(message.text)
        except (IncidentExtractionError, QwenClientError, ValueError):
            extraction_error = EXTRACTION_UNAVAILABLE_ERROR

        reply_text = build_telegram_reply_text(extraction, extraction_error)
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
        telegram_reply_sent=telegram_reply_sent,
        telegram_reply_error=telegram_reply_error,
    )


def build_telegram_reply_text(
    extraction: IncidentExtractionResult | None,
    extraction_error: str | None,
) -> str:
    """Build a concise Telegram reply from extraction output or safe error state."""

    if extraction_error or extraction is None:
        return "I received your message, but I could not extract the incident details yet. Please send the location and what help is needed."

    if not extraction.is_incident:
        return extraction.rejection_reason or "I can only process incident reports right now. Please send what happened, where it happened, and what help is needed."

    if extraction.should_ask_follow_up and extraction.follow_up_question:
        return extraction.follow_up_question

    reply_lines = ["Incident report received."]

    if extraction.summary:
        reply_lines.append(f"Summary: {extraction.summary}")
    if extraction.location_text:
        reply_lines.append(f"Location: {extraction.location_text}")
    if extraction.urgency:
        reply_lines.append(f"Urgency: {extraction.urgency}")
    if extraction.needs:
        reply_lines.append(f"Needs: {', '.join(extraction.needs)}")

    reply_lines.append("I will keep tracking this report while dispatch support is being prepared.")
    return "\n".join(reply_lines)
