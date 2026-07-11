from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.incident import IncidentExtractionResult
from app.schemas.telegram import TelegramWebhookAccepted, TelegramWebhookUpdate
from app.services.incident_auto_dispatch import (
    IncidentAutoDispatchError,
    IncidentAutoDispatchResult,
    IncidentAutoDispatchService,
)
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
NEW_COMMANDS = {"/new", "new"}
CANCEL_COMMANDS = {"/cancel", "cancel"}

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_incident_extraction_service() -> IncidentExtractionService:
    return IncidentExtractionService()


def get_incident_persistence_service(db: Session = Depends(get_db)) -> IncidentPersistenceService:
    return IncidentPersistenceService(db)


def get_incident_auto_dispatch_service(
    db: Session = Depends(get_db),
) -> IncidentAutoDispatchService | None:
    """Return automatic dispatch support only when the volunteer bot is configured."""

    if not settings.telegram_volunteer_bot_token.strip():
        return None
    return IncidentAutoDispatchService(
        db,
        TelegramBotClient(bot_token=settings.telegram_volunteer_bot_token),
    )


def get_telegram_bot_client() -> TelegramBotClient:
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
    auto_dispatch_service: IncidentAutoDispatchService | None = Depends(get_incident_auto_dispatch_service),
    telegram_bot_client: TelegramBotClient = Depends(get_telegram_bot_client),
) -> TelegramWebhookAccepted:
    """Accept an incident Telegram update, preserve recent context, persist it, and reply."""

    message = update.message
    extraction: IncidentExtractionResult | None = None
    extraction_error: str | None = None
    persistence_result: IncidentPersistenceResult | None = None
    persistence_error: str | None = None
    dispatch_result: IncidentAutoDispatchResult | None = None
    telegram_reply_sent = False
    telegram_reply_error: str | None = None

    if message and message.text and message.text.strip():
        source_context = build_telegram_source_context(update)
        command = message.text.strip().lower().split(maxsplit=1)[0]

        if command in NEW_COMMANDS or command in CANCEL_COMMANDS:
            try:
                resetter = getattr(incident_persistence_service, "close_pending_incident", None)
                closed = bool(resetter(source_context.source, source_context.source_chat_id)) if callable(resetter) else False
                reply_text = build_conversation_command_reply(command, closed)
            except (IncidentPersistenceError, ValueError):
                persistence_error = INCIDENT_PERSISTENCE_UNAVAILABLE_ERROR
                reply_text = "I could not reset the current report. Please try again."
        else:
            try:
                context_builder = getattr(incident_persistence_service, "build_extraction_text", None)
                extraction_text = context_builder(source_context) if callable(context_builder) else source_context.raw_text
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

            if (
                persistence_result is not None
                and persistence_result.status == "ready_for_dispatch"
                and auto_dispatch_service is not None
            ):
                try:
                    dispatch_result = auto_dispatch_service.dispatch_ready_incident(
                        persistence_result.incident_id
                    )
                except IncidentAutoDispatchError:
                    dispatch_result = None

            reply_text = build_telegram_reply_text(
                extraction,
                extraction_error,
                persistence_result,
                persistence_error,
                dispatch_result,
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


def build_conversation_command_reply(command: str, closed: bool) -> str:
    """Return a user-facing reply for /new or /cancel."""

    if command in NEW_COMMANDS:
        if closed:
            return "The previous unfinished report was closed. Send the new incident details now."
        return "No unfinished report was active. Send the new incident details now."
    if closed:
        return "The unfinished incident report was cancelled."
    return "There is no unfinished incident report to cancel."


def build_telegram_reply_text(
    extraction: IncidentExtractionResult | None,
    extraction_error: str | None,
    persistence_result: IncidentPersistenceResult | None = None,
    persistence_error: str | None = None,
    dispatch_result: IncidentAutoDispatchResult | None = None,
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
            "You can send /cancel to discard this unfinished report or /new to start over.\n"
            "If there is immediate danger, contact local emergency services now."
        )

    if dispatch_result and dispatch_result.sent:
        return (
            "Your emergency report has been received and saved. "
            "An available volunteer has been notified. "
            "A responder has not yet confirmed arrival. "
            "If there is immediate danger, contact local emergency services now."
        )

    if dispatch_result and dispatch_result.reason == "no_available_volunteer":
        return (
            "Your emergency report has been received and saved. "
            "No available volunteer was found yet. "
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
