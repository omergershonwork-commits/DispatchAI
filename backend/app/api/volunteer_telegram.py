from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.telegram import TelegramWebhookUpdate
from app.schemas.volunteer import VolunteerWebhookAccepted
from app.services.telegram_bot_client import TelegramBotClient, TelegramBotClientError
from app.services.volunteer_management import (
    VolunteerCommandResult,
    VolunteerManagementError,
    VolunteerManagementService,
    VolunteerSourceContext,
)

VOLUNTEER_COMMAND_UNAVAILABLE_ERROR = "volunteer_command_unavailable"
"""Safe response code returned when volunteer command processing fails."""

VOLUNTEER_REPLY_UNAVAILABLE_ERROR = "volunteer_reply_unavailable"
"""Safe response code returned when volunteer bot reply sending fails."""

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
"""Router containing volunteer Telegram webhook endpoints."""


def get_volunteer_management_service(db: Session = Depends(get_db)) -> VolunteerManagementService:
    """Return the volunteer management service used by volunteer bot ingestion."""

    return VolunteerManagementService(db)


def get_volunteer_telegram_bot_client() -> TelegramBotClient:
    """Return the Telegram Bot API client used for volunteer bot replies."""

    return TelegramBotClient(bot_token=settings.telegram_volunteer_bot_token)


@router.post(
    "/telegram/volunteers",
    response_model=VolunteerWebhookAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def receive_volunteer_telegram_webhook(
    update: TelegramWebhookUpdate,
    volunteer_service: VolunteerManagementService = Depends(get_volunteer_management_service),
    telegram_bot_client: TelegramBotClient = Depends(get_volunteer_telegram_bot_client),
) -> VolunteerWebhookAccepted:
    """Accept a volunteer Telegram webhook update and process registration commands."""

    message = update.message
    command_result: VolunteerCommandResult | None = None
    command_error: str | None = None
    telegram_reply_sent = False
    telegram_reply_error: str | None = None

    if message and message.text and message.text.strip():
        try:
            command_result = volunteer_service.process_message(
                build_volunteer_source_context(update),
            )
        except (VolunteerManagementError, ValueError):
            command_error = VOLUNTEER_COMMAND_UNAVAILABLE_ERROR
            command_result = VolunteerCommandResult(
                volunteer_id=None,
                volunteer_status=None,
                dispatch_id=None,
                reply_text="Volunteer command could not be processed right now. Please try again later.",
            )

        try:
            telegram_bot_client.send_message(message.chat.id, command_result.reply_text)
            telegram_reply_sent = True
        except (TelegramBotClientError, ValueError):
            telegram_reply_error = VOLUNTEER_REPLY_UNAVAILABLE_ERROR

    return VolunteerWebhookAccepted(
        update_id=update.update_id,
        message_id=message.message_id if message else None,
        chat_id=message.chat.id if message else None,
        has_text=bool(message and message.text),
        volunteer_id=command_result.volunteer_id if command_result else None,
        volunteer_status=command_result.volunteer_status if command_result else None,
        dispatch_id=command_result.dispatch_id if command_result else None,
        command_error=command_error,
        telegram_reply_sent=telegram_reply_sent,
        telegram_reply_error=telegram_reply_error,
    )


def build_volunteer_source_context(update: TelegramWebhookUpdate) -> VolunteerSourceContext:
    """Translate a Telegram volunteer update into generic volunteer source metadata."""

    message = update.message
    if message is None or message.text is None:
        raise ValueError("Telegram text message is required to build volunteer source context.")

    sender = message.from_
    return VolunteerSourceContext(
        source="telegram",
        source_chat_id=message.chat.id,
        source_user_id=sender.id if sender else None,
        source_username=sender.username if sender else message.chat.username,
        first_name=sender.first_name if sender else message.chat.first_name,
        last_name=sender.last_name if sender else message.chat.last_name,
        raw_text=message.text,
    )
