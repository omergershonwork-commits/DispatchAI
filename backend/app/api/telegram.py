from fastapi import APIRouter, status

from app.schemas.telegram import TelegramWebhookAccepted, TelegramWebhookUpdate

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/telegram",
    response_model=TelegramWebhookAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def receive_telegram_webhook(update: TelegramWebhookUpdate) -> TelegramWebhookAccepted:
    message = update.message

    return TelegramWebhookAccepted(
        update_id=update.update_id,
        message_id=message.message_id if message else None,
        chat_id=message.chat.id if message else None,
        has_text=bool(message and message.text),
    )
