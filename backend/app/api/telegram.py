from fastapi import APIRouter, status

from app.schemas.telegram import TelegramWebhookAccepted, TelegramWebhookUpdate

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
"""Router containing Telegram webhook ingestion endpoints."""


@router.post(
    "/telegram",
    response_model=TelegramWebhookAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def receive_telegram_webhook(update: TelegramWebhookUpdate) -> TelegramWebhookAccepted:
    """Accept a Telegram webhook update and return normalized ingestion metadata.

    This endpoint only validates and acknowledges the inbound Telegram payload.
    Later tasks will connect accepted updates to Qwen extraction, persistence,
    incident creation, and dispatch logic.
    """

    # Telegram message payload when this update includes a message.
    message = update.message

    return TelegramWebhookAccepted(
        update_id=update.update_id,
        message_id=message.message_id if message else None,
        chat_id=message.chat.id if message else None,
        has_text=bool(message and message.text),
    )
