from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.incident import Incident
from app.models.volunteer import Volunteer
from app.schemas.telegram import TelegramWebhookUpdate
from app.schemas.volunteer import VolunteerWebhookAccepted
from app.services.dispatch_lifecycle import DispatchLifecycleError, DispatchLifecycleService
from app.services.incident_assigned_forces import sync_assigned_force
from app.services.incident_auto_dispatch import IncidentAutoDispatchError, IncidentAutoDispatchService
from app.services.telegram_bot_client import TelegramBotClient, TelegramBotClientError
from app.services.volunteer_management import (
    VolunteerCommandResult,
    VolunteerManagementError,
    VolunteerManagementService,
    VolunteerSourceContext,
)

VOLUNTEER_COMMAND_UNAVAILABLE_ERROR = "volunteer_command_unavailable"
VOLUNTEER_REPLY_UNAVAILABLE_ERROR = "volunteer_reply_unavailable"

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_volunteer_management_service(db: Session = Depends(get_db)) -> VolunteerManagementService:
    return VolunteerManagementService(db)


def get_volunteer_telegram_bot_client() -> TelegramBotClient:
    return TelegramBotClient(bot_token=settings.telegram_volunteer_bot_token)


def get_incident_telegram_bot_client() -> TelegramBotClient | None:
    if not settings.telegram_incident_bot_token.strip():
        return None
    return TelegramBotClient(bot_token=settings.telegram_incident_bot_token)


def get_volunteer_auto_dispatch_service(
    db: Session = Depends(get_db),
) -> IncidentAutoDispatchService | None:
    if not settings.telegram_volunteer_bot_token.strip():
        return None
    return IncidentAutoDispatchService(
        db,
        TelegramBotClient(bot_token=settings.telegram_volunteer_bot_token),
    )


def get_dispatch_lifecycle_service(
    db: Session = Depends(get_db),
) -> DispatchLifecycleService:
    return DispatchLifecycleService(
        db,
        offer_timeout_seconds=settings.dispatch_offer_timeout_seconds,
    )


@router.post(
    "/telegram/volunteers",
    response_model=VolunteerWebhookAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def receive_volunteer_telegram_webhook(
    update: TelegramWebhookUpdate,
    volunteer_service: VolunteerManagementService = Depends(get_volunteer_management_service),
    lifecycle_service: DispatchLifecycleService = Depends(get_dispatch_lifecycle_service),
    telegram_bot_client: TelegramBotClient = Depends(get_volunteer_telegram_bot_client),
    incident_bot_client: TelegramBotClient | None = Depends(get_incident_telegram_bot_client),
    auto_dispatch_service: IncidentAutoDispatchService | None = Depends(
        get_volunteer_auto_dispatch_service
    ),
) -> VolunteerWebhookAccepted:
    """Process volunteer registration, offer decisions, and assignment progress."""

    message = update.message
    command_result: VolunteerCommandResult | None = None
    command_error: str | None = None
    telegram_reply_sent = False
    telegram_reply_error: str | None = None

    if message and message.text and message.text.strip():
        source_context = build_volunteer_source_context(update)
        try:
            command_result = lifecycle_service.process_progress_message(source_context)
            if command_result is None:
                command_result = volunteer_service.process_message(source_context)
            sync_volunteer_dashboard_state(volunteer_service.db, command_result)
        except (VolunteerManagementError, DispatchLifecycleError, ValueError):
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

        reporter_chat_id = command_result.reporter_chat_id
        reporter_reply_text = command_result.reporter_reply_text
        if command_result.dispatch_action == "done":
            completion_update = lifecycle_service.reporter_update_for_result(command_result)
            if completion_update is not None:
                reporter_chat_id, reporter_reply_text = completion_update

        if (
            command_result.reporter_source == "telegram"
            or command_result.dispatch_action == "done"
        ) and reporter_chat_id is not None and reporter_reply_text and incident_bot_client is not None:
            try:
                incident_bot_client.send_message(reporter_chat_id, reporter_reply_text)
            except (TelegramBotClientError, ValueError):
                pass

        if (
            command_result.dispatch_action == "declined"
            and command_result.incident_id is not None
            and auto_dispatch_service is not None
        ):
            try:
                dispatch_result = auto_dispatch_service.dispatch_ready_incident(command_result.incident_id)
                if (
                    dispatch_result.reason == "no_available_volunteer"
                    and incident_bot_client is not None
                ):
                    incident = auto_dispatch_service.db.get(Incident, command_result.incident_id)
                    if incident is not None and incident.source == "telegram":
                        incident_bot_client.send_message(
                            incident.source_chat_id,
                            "No registered volunteer has accepted yet. Your report remains saved. If there is immediate danger, contact local emergency services now.",
                        )
            except (IncidentAutoDispatchError, TelegramBotClientError, ValueError):
                pass

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


def sync_volunteer_dashboard_state(db: Session, result: VolunteerCommandResult) -> None:
    """Copy command results into dashboard-oriented volunteer and incident fields."""

    if result.volunteer_id is None:
        return
    try:
        volunteer = db.get(Volunteer, result.volunteer_id)
        if volunteer is None:
            return

        metadata = volunteer.metadata_json or {}
        stored_phone = metadata.get("phone_number")
        if stored_phone and not volunteer.phone_number:
            volunteer.phone_number = str(stored_phone)

        if result.dispatch_action in {"accepted", "declined", "done"} and result.incident_id is not None:
            incident = db.get(Incident, result.incident_id)
            sync_assigned_force(
                incident,
                volunteer,
                status=result.dispatch_action,
                dispatch_id=result.dispatch_id,
            )
            if result.dispatch_action == "done":
                volunteer.trust_score = min(1.0, float(volunteer.trust_score or 0.5) + 0.02)

        db.commit()
    except SQLAlchemyError:
        db.rollback()


def build_volunteer_source_context(update: TelegramWebhookUpdate) -> VolunteerSourceContext:
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
