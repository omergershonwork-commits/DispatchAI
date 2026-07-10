from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models.volunteer import (
    DISPATCH_STATUS_DONE,
    DISPATCH_STATUS_SENT,
    VOLUNTEER_STATUS_AVAILABLE,
    VOLUNTEER_STATUS_BUSY,
    VOLUNTEER_STATUS_INACTIVE,
    Volunteer,
    VolunteerDispatch,
    utc_now,
)

REGISTER_COMMANDS = {"/start", "/register", "register", "join"}
"""Text commands that register or reactivate a volunteer."""

DONE_COMMANDS = {"done", "/done", "finished", "complete", "completed"}
"""Text commands that mark the latest active dispatch as complete."""

STOP_COMMANDS = {"/stop", "stop", "pause", "inactive"}
"""Text commands that make a volunteer inactive."""

STATUS_COMMANDS = {"/status", "status"}
"""Text commands that return the current volunteer state."""


class VolunteerManagementError(RuntimeError):
    """Raised when volunteer registration or dispatch state updates fail."""


@dataclass(frozen=True)
class VolunteerSourceContext:
    """Source-agnostic volunteer metadata from an inbound channel."""

    source: str
    """Inbound source name, such as telegram or whatsapp."""

    source_chat_id: int
    """Conversation identifier used for volunteer messages."""

    source_user_id: int | None
    """Source-specific user identifier, when available."""

    source_username: str | None
    """Source-specific username, when available."""

    first_name: str | None
    """Source first name, when available."""

    last_name: str | None
    """Source last name, when available."""

    raw_text: str
    """Raw inbound message text."""


@dataclass(frozen=True)
class VolunteerCommandResult:
    """Result returned after processing a volunteer bot message."""

    volunteer_id: int | None
    """Volunteer identifier, when the message mapped to a registered volunteer."""

    volunteer_status: str | None
    """Volunteer status after command processing."""

    dispatch_id: int | None
    """Dispatch identifier affected by the command, when applicable."""

    reply_text: str
    """Plain-text reply that should be sent to the volunteer."""


@dataclass(frozen=True)
class VolunteerDispatchRequestResult:
    """Result returned after creating a volunteer dispatch request."""

    volunteer_id: int
    """Volunteer that should receive the dispatch message."""

    source: str
    """Volunteer source channel."""

    source_chat_id: int
    """Source chat id used to send the dispatch message."""

    dispatch_id: int
    """Persisted dispatch request identifier."""

    message_text: str
    """Message that should be sent to the volunteer."""


class VolunteerManagementService:
    """Manage volunteer registration and dispatch lifecycle state."""

    def __init__(self, db: Session) -> None:
        """Create a volunteer management service bound to one DB session."""

        self.db = db

    def process_message(self, source_context: VolunteerSourceContext) -> VolunteerCommandResult:
        """Process a source-agnostic volunteer bot message."""

        command = source_context.raw_text.strip().lower()
        first_word = command.split(maxsplit=1)[0] if command else ""

        try:
            self._ensure_schema()
            if first_word in REGISTER_COMMANDS:
                return self._register_or_reactivate(source_context)
            if first_word in DONE_COMMANDS:
                return self._mark_latest_dispatch_done(source_context)
            if first_word in STOP_COMMANDS:
                return self._mark_inactive(source_context)
            if first_word in STATUS_COMMANDS:
                return self._status(source_context)
            return self._unknown_command(source_context)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise VolunteerManagementError("Volunteer command processing failed.") from exc

    def create_dispatch_request(
        self,
        volunteer_id: int,
        message_text: str,
        incident_id: int | None = None,
    ) -> VolunteerDispatchRequestResult:
        """Create a pending dispatch request for a registered volunteer."""

        if not message_text.strip():
            raise ValueError("Volunteer dispatch message must not be empty.")

        try:
            self._ensure_schema()
            volunteer = self.db.get(Volunteer, volunteer_id)
            if volunteer is None:
                raise ValueError("Volunteer was not found.")
            if volunteer.status == VOLUNTEER_STATUS_INACTIVE:
                raise ValueError("Inactive volunteer cannot receive dispatch requests.")

            dispatch = VolunteerDispatch(
                volunteer_id=volunteer.id,
                incident_id=incident_id,
                message_text=message_text.strip(),
                status=DISPATCH_STATUS_SENT,
            )
            volunteer.status = VOLUNTEER_STATUS_BUSY
            volunteer.last_seen_at = utc_now()
            self.db.add(dispatch)
            self.db.commit()
            self.db.refresh(dispatch)
            self.db.refresh(volunteer)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise VolunteerManagementError("Volunteer dispatch creation failed.") from exc

        return VolunteerDispatchRequestResult(
            volunteer_id=volunteer.id,
            source=volunteer.source,
            source_chat_id=volunteer.source_chat_id,
            dispatch_id=dispatch.id,
            message_text=dispatch.message_text,
        )

    def _ensure_schema(self) -> None:
        """Create known ORM tables when running without migrations in local/dev mode."""

        Base.metadata.create_all(bind=self.db.get_bind())

    def _register_or_reactivate(self, source_context: VolunteerSourceContext) -> VolunteerCommandResult:
        """Create or reactivate a volunteer for the source conversation."""

        volunteer = self._find_volunteer(source_context)
        created = volunteer is None
        if volunteer is None:
            volunteer = Volunteer(
                source=source_context.source,
                source_chat_id=source_context.source_chat_id,
                status=VOLUNTEER_STATUS_AVAILABLE,
            )
            self.db.add(volunteer)

        self._apply_source_context(volunteer, source_context)
        volunteer.status = VOLUNTEER_STATUS_AVAILABLE
        self.db.commit()
        self.db.refresh(volunteer)

        action = "registered" if created else "reactivated"
        return VolunteerCommandResult(
            volunteer_id=volunteer.id,
            volunteer_status=volunteer.status,
            dispatch_id=None,
            reply_text=f"Volunteer {action}. You will receive dispatch messages here when help is needed.",
        )

    def _mark_latest_dispatch_done(self, source_context: VolunteerSourceContext) -> VolunteerCommandResult:
        """Mark the latest active dispatch for this volunteer as done."""

        volunteer = self._find_volunteer(source_context)
        if volunteer is None:
            return VolunteerCommandResult(
                volunteer_id=None,
                volunteer_status=None,
                dispatch_id=None,
                reply_text="You are not registered yet. Send /register to join as a volunteer.",
            )

        self._apply_source_context(volunteer, source_context)
        dispatch = self._find_latest_active_dispatch(volunteer.id)
        if dispatch is None:
            volunteer.status = VOLUNTEER_STATUS_AVAILABLE
            self.db.commit()
            self.db.refresh(volunteer)
            return VolunteerCommandResult(
                volunteer_id=volunteer.id,
                volunteer_status=volunteer.status,
                dispatch_id=None,
                reply_text="No active dispatch is assigned to you right now.",
            )

        dispatch.status = DISPATCH_STATUS_DONE
        dispatch.completed_at = utc_now()
        volunteer.status = VOLUNTEER_STATUS_AVAILABLE
        self.db.commit()
        self.db.refresh(volunteer)
        self.db.refresh(dispatch)

        return VolunteerCommandResult(
            volunteer_id=volunteer.id,
            volunteer_status=volunteer.status,
            dispatch_id=dispatch.id,
            reply_text=f"Dispatch #{dispatch.id} marked done. Thank you.",
        )

    def _mark_inactive(self, source_context: VolunteerSourceContext) -> VolunteerCommandResult:
        """Mark a registered volunteer inactive."""

        volunteer = self._find_volunteer(source_context)
        if volunteer is None:
            return VolunteerCommandResult(
                volunteer_id=None,
                volunteer_status=None,
                dispatch_id=None,
                reply_text="You are not registered yet. Send /register to join as a volunteer.",
            )

        self._apply_source_context(volunteer, source_context)
        volunteer.status = VOLUNTEER_STATUS_INACTIVE
        self.db.commit()
        self.db.refresh(volunteer)
        return VolunteerCommandResult(
            volunteer_id=volunteer.id,
            volunteer_status=volunteer.status,
            dispatch_id=None,
            reply_text="Volunteer status set to inactive. Send /register to become available again.",
        )

    def _status(self, source_context: VolunteerSourceContext) -> VolunteerCommandResult:
        """Return the current volunteer status."""

        volunteer = self._find_volunteer(source_context)
        if volunteer is None:
            return VolunteerCommandResult(
                volunteer_id=None,
                volunteer_status=None,
                dispatch_id=None,
                reply_text="You are not registered yet. Send /register to join as a volunteer.",
            )

        self._apply_source_context(volunteer, source_context)
        self.db.commit()
        self.db.refresh(volunteer)
        return VolunteerCommandResult(
            volunteer_id=volunteer.id,
            volunteer_status=volunteer.status,
            dispatch_id=None,
            reply_text=f"Volunteer status: {volunteer.status}.",
        )

    def _unknown_command(self, source_context: VolunteerSourceContext) -> VolunteerCommandResult:
        """Return guidance for unsupported volunteer bot text."""

        volunteer = self._find_volunteer(source_context)
        if volunteer is not None:
            self._apply_source_context(volunteer, source_context)
            self.db.commit()
            self.db.refresh(volunteer)
            volunteer_id = volunteer.id
            volunteer_status = volunteer.status
        else:
            volunteer_id = None
            volunteer_status = None

        return VolunteerCommandResult(
            volunteer_id=volunteer_id,
            volunteer_status=volunteer_status,
            dispatch_id=None,
            reply_text="Volunteer bot commands: /register, /status, done, /stop.",
        )

    def _find_volunteer(self, source_context: VolunteerSourceContext) -> Volunteer | None:
        """Return the volunteer for a source conversation, when registered."""

        return (
            self.db.query(Volunteer)
            .filter(
                Volunteer.source == source_context.source,
                Volunteer.source_chat_id == source_context.source_chat_id,
            )
            .first()
        )

    def _find_latest_active_dispatch(self, volunteer_id: int) -> VolunteerDispatch | None:
        """Return the latest active dispatch for a volunteer, when one exists."""

        return (
            self.db.query(VolunteerDispatch)
            .filter(
                VolunteerDispatch.volunteer_id == volunteer_id,
                VolunteerDispatch.status == DISPATCH_STATUS_SENT,
            )
            .order_by(VolunteerDispatch.sent_at.desc(), VolunteerDispatch.id.desc())
            .first()
        )

    def _apply_source_context(self, volunteer: Volunteer, source_context: VolunteerSourceContext) -> None:
        """Copy latest source metadata onto a volunteer row."""

        volunteer.source_user_id = source_context.source_user_id
        volunteer.source_username = source_context.source_username
        volunteer.first_name = source_context.first_name
        volunteer.last_name = source_context.last_name
        volunteer.display_name = self._display_name(source_context)
        volunteer.last_seen_at = utc_now()

    def _display_name(self, source_context: VolunteerSourceContext) -> str | None:
        """Return a readable display name from source metadata."""

        parts = [source_context.first_name, source_context.last_name]
        display_name = " ".join(part.strip() for part in parts if part and part.strip())
        if display_name:
            return display_name
        return source_context.source_username
