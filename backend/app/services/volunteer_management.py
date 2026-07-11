from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models.incident import (
    INCIDENT_STATUS_DISPATCHED,
    INCIDENT_STATUS_READY_FOR_DISPATCH,
    Incident,
)
from app.models.volunteer import (
    DISPATCH_STATUS_ACCEPTED,
    DISPATCH_STATUS_DECLINED,
    DISPATCH_STATUS_DONE,
    DISPATCH_STATUS_SENT,
    VOLUNTEER_STATUS_AVAILABLE,
    VOLUNTEER_STATUS_BUSY,
    VOLUNTEER_STATUS_INACTIVE,
    VOLUNTEER_STATUS_PENDING_RESPONSE,
    Volunteer,
    VolunteerDispatch,
    utc_now,
)

REGISTER_COMMANDS = {"/start", "/register", "register", "join"}
ACCEPT_COMMANDS = {"accept", "/accept", "yes", "i accept", "i can come", "coming", "on my way"}
DECLINE_COMMANDS = {
    "decline",
    "/decline",
    "reject",
    "/reject",
    "no",
    "i cant come",
    "i can't come",
    "i cannot come",
    "cant come",
    "can't come",
    "not available",
    "unavailable",
}
DONE_COMMANDS = {"done", "/done", "finished", "complete", "completed"}
STOP_COMMANDS = {"/stop", "stop", "pause", "inactive"}
STATUS_COMMANDS = {"/status", "status"}
CANCEL_COMMANDS = {"/cancel", "cancel"}

REGISTRATION_STEPS = (
    "full_name",
    "service_area",
    "skills",
    "vehicle",
    "max_distance_km",
    "phone_number",
    "availability",
)

REGISTRATION_QUESTIONS = {
    "full_name": "Registration 1/7: What is your full name?",
    "service_area": "Registration 2/7: What city or area are you currently available in?",
    "skills": (
        "Registration 3/7: What can you help with? Send comma-separated skills, "
        "for example: medical, rescue, transport, logistics."
    ),
    "vehicle": "Registration 4/7: What vehicle do you have? Send car, motorcycle, truck, bicycle, or none.",
    "max_distance_km": "Registration 5/7: What maximum distance in kilometers can you travel?",
    "phone_number": "Registration 6/7: What phone number can dispatch use to contact you?",
    "availability": "Registration 7/7: Are you available now? Reply yes or no.",
}


class VolunteerManagementError(RuntimeError):
    """Raised when volunteer registration or dispatch state updates fail."""


@dataclass(frozen=True)
class VolunteerSourceContext:
    source: str
    source_chat_id: int
    source_user_id: int | None
    source_username: str | None
    first_name: str | None
    last_name: str | None
    raw_text: str


@dataclass(frozen=True)
class VolunteerCommandResult:
    volunteer_id: int | None
    volunteer_status: str | None
    dispatch_id: int | None
    reply_text: str
    incident_id: int | None = None
    dispatch_action: str | None = None
    reporter_source: str | None = None
    reporter_chat_id: int | None = None
    reporter_reply_text: str | None = None


@dataclass(frozen=True)
class VolunteerDispatchRequestResult:
    volunteer_id: int
    source: str
    source_chat_id: int
    dispatch_id: int
    message_text: str


class VolunteerManagementService:
    """Manage volunteer registration profiles and dispatch lifecycle state."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def process_message(self, source_context: VolunteerSourceContext) -> VolunteerCommandResult:
        text = source_context.raw_text.strip()
        command = text.lower()
        first_word = command.split(maxsplit=1)[0] if command else ""

        try:
            self._ensure_schema()
            volunteer = self._find_volunteer(source_context)
            active_offer = self._find_latest_dispatch(volunteer.id, DISPATCH_STATUS_SENT) if volunteer else None

            if active_offer is not None:
                if self._matches_command(command, first_word, ACCEPT_COMMANDS):
                    return self._accept_dispatch(volunteer, active_offer, source_context)
                if (
                    self._matches_command(command, first_word, DECLINE_COMMANDS)
                    or first_word in CANCEL_COMMANDS
                ):
                    return self._decline_dispatch(volunteer, active_offer, source_context)
                if first_word in STATUS_COMMANDS:
                    return self._status(source_context)
                return VolunteerCommandResult(
                    volunteer.id,
                    volunteer.status,
                    active_offer.id,
                    "A dispatch offer is waiting for your response. Reply accept or decline.",
                    incident_id=active_offer.incident_id,
                    dispatch_action="awaiting_response",
                )

            if first_word in REGISTER_COMMANDS:
                return self._start_or_resume_registration(source_context)
            if first_word in DONE_COMMANDS:
                return self._mark_latest_dispatch_done(source_context)
            if first_word in STOP_COMMANDS:
                return self._mark_inactive(source_context)
            if first_word in STATUS_COMMANDS:
                return self._status(source_context)
            if first_word in CANCEL_COMMANDS:
                return self._cancel_registration(source_context)

            if volunteer is not None and self._registration_step(volunteer):
                return self._process_registration_answer(volunteer, source_context)
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
        """Create a pending offer for one fully registered available volunteer."""

        if not message_text.strip():
            raise ValueError("Volunteer dispatch message must not be empty.")

        try:
            self._ensure_schema()
            volunteer = self.db.get(Volunteer, volunteer_id)
            if volunteer is None:
                raise ValueError("Volunteer was not found.")
            if not self._registration_complete(volunteer):
                raise ValueError("Volunteer registration is incomplete.")
            if volunteer.status != VOLUNTEER_STATUS_AVAILABLE:
                raise ValueError("Volunteer is not currently available.")
            if self._find_any_open_dispatch(volunteer.id) is not None:
                raise ValueError("Volunteer already has an open dispatch.")

            dispatch = VolunteerDispatch(
                volunteer_id=volunteer.id,
                incident_id=incident_id,
                message_text=message_text.strip(),
                status=DISPATCH_STATUS_SENT,
            )
            volunteer.status = VOLUNTEER_STATUS_PENDING_RESPONSE
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
        Base.metadata.create_all(bind=self.db.get_bind())

    def _matches_command(self, command: str, first_word: str, commands: set[str]) -> bool:
        return command in commands or first_word in commands

    def _accept_dispatch(
        self,
        volunteer: Volunteer,
        dispatch: VolunteerDispatch,
        source_context: VolunteerSourceContext,
    ) -> VolunteerCommandResult:
        self._apply_source_context(volunteer, source_context)
        dispatch.status = DISPATCH_STATUS_ACCEPTED
        metadata = dict(dispatch.metadata_json or {})
        metadata["accepted_at"] = utc_now().isoformat()
        dispatch.metadata_json = metadata
        volunteer.status = VOLUNTEER_STATUS_BUSY

        incident = self.db.get(Incident, dispatch.incident_id) if dispatch.incident_id is not None else None
        if incident is not None:
            incident.status = INCIDENT_STATUS_DISPATCHED

        self.db.commit()
        self.db.refresh(dispatch)
        self.db.refresh(volunteer)

        display_name = volunteer.display_name or volunteer.source_username or f"Volunteer {volunteer.id}"
        reporter_reply = None
        reporter_source = None
        reporter_chat_id = None
        if incident is not None:
            reporter_source = incident.source
            reporter_chat_id = incident.source_chat_id
            reporter_reply = (
                f"Volunteer {display_name} accepted your request and is responding. "
                "Keep this chat available for updates."
            )

        return VolunteerCommandResult(
            volunteer.id,
            volunteer.status,
            dispatch.id,
            "Dispatch accepted. You are now assigned. Reply done when the assignment is complete.",
            incident_id=dispatch.incident_id,
            dispatch_action="accepted",
            reporter_source=reporter_source,
            reporter_chat_id=reporter_chat_id,
            reporter_reply_text=reporter_reply,
        )

    def _decline_dispatch(
        self,
        volunteer: Volunteer,
        dispatch: VolunteerDispatch,
        source_context: VolunteerSourceContext,
    ) -> VolunteerCommandResult:
        self._apply_source_context(volunteer, source_context)
        dispatch.status = DISPATCH_STATUS_DECLINED
        metadata = dict(dispatch.metadata_json or {})
        metadata["declined_at"] = utc_now().isoformat()
        metadata["decline_text"] = source_context.raw_text.strip()
        dispatch.metadata_json = metadata
        volunteer.status = VOLUNTEER_STATUS_AVAILABLE

        incident = self.db.get(Incident, dispatch.incident_id) if dispatch.incident_id is not None else None
        if incident is not None:
            incident.status = INCIDENT_STATUS_READY_FOR_DISPATCH

        self.db.commit()
        self.db.refresh(dispatch)
        self.db.refresh(volunteer)
        return VolunteerCommandResult(
            volunteer.id,
            volunteer.status,
            dispatch.id,
            "Dispatch declined. You remain available for other assignments.",
            incident_id=dispatch.incident_id,
            dispatch_action="declined",
        )

    def _start_or_resume_registration(self, source_context: VolunteerSourceContext) -> VolunteerCommandResult:
        volunteer = self._find_volunteer(source_context)
        if volunteer is None:
            volunteer = Volunteer(
                source=source_context.source,
                source_chat_id=source_context.source_chat_id,
                status=VOLUNTEER_STATUS_INACTIVE,
                metadata_json={"registration_step": "full_name", "registration_complete": False},
            )
            self.db.add(volunteer)

        open_dispatch = self._find_any_open_dispatch(volunteer.id) if volunteer.id else None
        if open_dispatch is not None:
            return VolunteerCommandResult(
                volunteer.id,
                volunteer.status,
                open_dispatch.id,
                "You already have an active dispatch. Reply done when complete, or respond to the pending offer.",
                incident_id=open_dispatch.incident_id,
            )

        self._apply_source_context(volunteer, source_context)
        metadata = dict(volunteer.metadata_json or {})

        if metadata.get("registration_complete"):
            volunteer.status = VOLUNTEER_STATUS_AVAILABLE
            metadata["available_now"] = True
            metadata["registration_step"] = None
            volunteer.metadata_json = metadata
            self.db.commit()
            self.db.refresh(volunteer)
            return VolunteerCommandResult(
                volunteer.id,
                volunteer.status,
                None,
                "Your volunteer profile is complete and you are now available. Send /status to review it or /stop to pause assignments.",
            )

        step = metadata.get("registration_step") or "full_name"
        metadata["registration_step"] = step
        metadata["registration_complete"] = False
        volunteer.metadata_json = metadata
        volunteer.status = VOLUNTEER_STATUS_INACTIVE
        self.db.commit()
        self.db.refresh(volunteer)
        return VolunteerCommandResult(
            volunteer.id,
            volunteer.status,
            None,
            "Welcome to volunteer registration. I will ask a few details so dispatch can match you safely.\n"
            f"{REGISTRATION_QUESTIONS[step]}",
        )

    def _process_registration_answer(
        self,
        volunteer: Volunteer,
        source_context: VolunteerSourceContext,
    ) -> VolunteerCommandResult:
        self._apply_source_context(volunteer, source_context)
        metadata = dict(volunteer.metadata_json or {})
        step = self._registration_step(volunteer)
        if step is None:
            return self._unknown_command(source_context)

        answer = source_context.raw_text.strip()
        validation_error = self._apply_registration_answer(volunteer, metadata, step, answer)
        if validation_error:
            self.db.commit()
            return VolunteerCommandResult(
                volunteer.id,
                volunteer.status,
                None,
                f"{validation_error}\n{REGISTRATION_QUESTIONS[step]}",
            )

        next_step = self._next_registration_step(step)
        if next_step is not None:
            metadata["registration_step"] = next_step
            volunteer.metadata_json = metadata
            volunteer.status = VOLUNTEER_STATUS_INACTIVE
            self.db.commit()
            self.db.refresh(volunteer)
            return VolunteerCommandResult(
                volunteer.id,
                volunteer.status,
                None,
                REGISTRATION_QUESTIONS[next_step],
            )

        metadata["registration_step"] = None
        metadata["registration_complete"] = True
        available_now = bool(metadata.get("available_now"))
        volunteer.metadata_json = metadata
        volunteer.status = VOLUNTEER_STATUS_AVAILABLE if available_now else VOLUNTEER_STATUS_INACTIVE
        self.db.commit()
        self.db.refresh(volunteer)
        return VolunteerCommandResult(
            volunteer.id,
            volunteer.status,
            None,
            "Registration complete. Your area, skills, vehicle, travel distance, contact number, and availability were saved. "
            f"Current status: {volunteer.status}.",
        )

    def _apply_registration_answer(
        self,
        volunteer: Volunteer,
        metadata: dict,
        step: str,
        answer: str,
    ) -> str | None:
        if step == "full_name":
            if len(answer) < 2:
                return "Please send your full name."
            volunteer.display_name = answer
        elif step == "service_area":
            if len(answer) < 2:
                return "Please send a city, neighborhood, or service area."
            metadata["service_areas"] = [answer]
            metadata["location_text"] = answer
        elif step == "skills":
            skills = [item.strip().lower().replace(" ", "_") for item in answer.split(",") if item.strip()]
            if not skills:
                return "Please send at least one skill."
            metadata["skills"] = skills
        elif step == "vehicle":
            if not answer:
                return "Please send your vehicle type or none."
            metadata["vehicle"] = answer.lower()
        elif step == "max_distance_km":
            try:
                distance = float(answer.replace("km", "").strip())
            except ValueError:
                return "Please send a number of kilometers, for example 10."
            if distance <= 0 or distance > 500:
                return "Please send a distance between 1 and 500 kilometers."
            metadata["max_distance_km"] = distance
        elif step == "phone_number":
            digits = "".join(character for character in answer if character.isdigit())
            if len(digits) < 7:
                return "Please send a valid phone number."
            metadata["phone_number"] = answer
        elif step == "availability":
            normalized = answer.lower()
            if normalized in {"yes", "y", "available", "כן"}:
                metadata["available_now"] = True
            elif normalized in {"no", "n", "not available", "לא"}:
                metadata["available_now"] = False
            else:
                return "Please reply yes or no."
        volunteer.metadata_json = metadata
        return None

    def _next_registration_step(self, current_step: str) -> str | None:
        index = REGISTRATION_STEPS.index(current_step)
        return REGISTRATION_STEPS[index + 1] if index + 1 < len(REGISTRATION_STEPS) else None

    def _registration_step(self, volunteer: Volunteer) -> str | None:
        step = (volunteer.metadata_json or {}).get("registration_step")
        return step if step in REGISTRATION_STEPS else None

    def _registration_complete(self, volunteer: Volunteer) -> bool:
        return bool((volunteer.metadata_json or {}).get("registration_complete"))

    def _cancel_registration(self, source_context: VolunteerSourceContext) -> VolunteerCommandResult:
        volunteer = self._find_volunteer(source_context)
        if volunteer is None or self._registration_step(volunteer) is None:
            return VolunteerCommandResult(
                volunteer.id if volunteer else None,
                volunteer.status if volunteer else None,
                None,
                "No registration is currently active.",
            )
        metadata = dict(volunteer.metadata_json or {})
        metadata["registration_step"] = None
        volunteer.metadata_json = metadata
        volunteer.status = VOLUNTEER_STATUS_INACTIVE
        self.db.commit()
        return VolunteerCommandResult(
            volunteer.id,
            volunteer.status,
            None,
            "Registration paused. Send /register to continue.",
        )

    def _mark_latest_dispatch_done(self, source_context: VolunteerSourceContext) -> VolunteerCommandResult:
        volunteer = self._find_volunteer(source_context)
        if volunteer is None:
            return VolunteerCommandResult(None, None, None, "You are not registered yet. Send /register to join as a volunteer.")

        self._apply_source_context(volunteer, source_context)
        dispatch = self._find_latest_dispatch(volunteer.id, DISPATCH_STATUS_ACCEPTED)
        if dispatch is None:
            self.db.commit()
            return VolunteerCommandResult(
                volunteer.id,
                volunteer.status,
                None,
                "No accepted dispatch is assigned to you right now.",
            )

        dispatch.status = DISPATCH_STATUS_DONE
        dispatch.completed_at = utc_now()
        volunteer.status = VOLUNTEER_STATUS_AVAILABLE
        self.db.commit()
        self.db.refresh(volunteer)
        self.db.refresh(dispatch)
        return VolunteerCommandResult(
            volunteer.id,
            volunteer.status,
            dispatch.id,
            "The dispatch has been marked complete. Thank you. You are available for new assignments.",
            incident_id=dispatch.incident_id,
            dispatch_action="done",
        )

    def _mark_inactive(self, source_context: VolunteerSourceContext) -> VolunteerCommandResult:
        volunteer = self._find_volunteer(source_context)
        if volunteer is None:
            return VolunteerCommandResult(None, None, None, "You are not registered yet. Send /register to join as a volunteer.")
        open_dispatch = self._find_any_open_dispatch(volunteer.id)
        if open_dispatch is not None:
            return VolunteerCommandResult(
                volunteer.id,
                volunteer.status,
                open_dispatch.id,
                "You have an active dispatch. Decline a pending offer or reply done after completing an accepted assignment.",
                incident_id=open_dispatch.incident_id,
            )
        self._apply_source_context(volunteer, source_context)
        metadata = dict(volunteer.metadata_json or {})
        metadata["available_now"] = False
        volunteer.metadata_json = metadata
        volunteer.status = VOLUNTEER_STATUS_INACTIVE
        self.db.commit()
        return VolunteerCommandResult(
            volunteer.id,
            volunteer.status,
            None,
            "You are now inactive and will not receive new assignments. Send /register to reactivate.",
        )

    def _status(self, source_context: VolunteerSourceContext) -> VolunteerCommandResult:
        volunteer = self._find_volunteer(source_context)
        if volunteer is None:
            return VolunteerCommandResult(None, None, None, "You are not registered yet. Send /register to join as a volunteer.")

        self._apply_source_context(volunteer, source_context)
        step = self._registration_step(volunteer)
        if step:
            self.db.commit()
            return VolunteerCommandResult(
                volunteer.id,
                volunteer.status,
                None,
                f"Registration is incomplete. {REGISTRATION_QUESTIONS[step]}",
            )

        open_dispatch = self._find_any_open_dispatch(volunteer.id)
        dispatch_line = ""
        if open_dispatch is not None:
            if open_dispatch.status == DISPATCH_STATUS_SENT:
                dispatch_line = f"\nPending offer: dispatch #{open_dispatch.id}. Reply accept or decline."
            else:
                dispatch_line = f"\nAccepted assignment: dispatch #{open_dispatch.id}. Reply done when complete."

        metadata = volunteer.metadata_json or {}
        skills = ", ".join(metadata.get("skills", [])) or "not provided"
        areas = ", ".join(metadata.get("service_areas", [])) or "not provided"
        vehicle = metadata.get("vehicle", "not provided")
        distance = metadata.get("max_distance_km", "not provided")
        self.db.commit()
        return VolunteerCommandResult(
            volunteer.id,
            volunteer.status,
            open_dispatch.id if open_dispatch else None,
            (
                f"Volunteer status: {volunteer.status}.\n"
                f"Name: {volunteer.display_name or 'not provided'}\n"
                f"Area: {areas}\nSkills: {skills}\nVehicle: {vehicle}\n"
                f"Maximum distance: {distance} km.{dispatch_line}"
            ),
            incident_id=open_dispatch.incident_id if open_dispatch else None,
        )

    def _unknown_command(self, source_context: VolunteerSourceContext) -> VolunteerCommandResult:
        volunteer = self._find_volunteer(source_context)
        if volunteer is not None:
            self._apply_source_context(volunteer, source_context)
            self.db.commit()
        return VolunteerCommandResult(
            volunteer.id if volunteer else None,
            volunteer.status if volunteer else None,
            None,
            "Volunteer bot commands: /register, /status, accept, decline, done, /stop, /cancel.",
        )

    def _find_volunteer(self, source_context: VolunteerSourceContext) -> Volunteer | None:
        return (
            self.db.query(Volunteer)
            .filter(
                Volunteer.source == source_context.source,
                Volunteer.source_chat_id == source_context.source_chat_id,
            )
            .first()
        )

    def _find_latest_dispatch(self, volunteer_id: int, status: str) -> VolunteerDispatch | None:
        return (
            self.db.query(VolunteerDispatch)
            .filter(
                VolunteerDispatch.volunteer_id == volunteer_id,
                VolunteerDispatch.status == status,
            )
            .order_by(VolunteerDispatch.sent_at.desc(), VolunteerDispatch.id.desc())
            .first()
        )

    def _find_any_open_dispatch(self, volunteer_id: int) -> VolunteerDispatch | None:
        return (
            self.db.query(VolunteerDispatch)
            .filter(
                VolunteerDispatch.volunteer_id == volunteer_id,
                VolunteerDispatch.status.in_([DISPATCH_STATUS_SENT, DISPATCH_STATUS_ACCEPTED]),
            )
            .order_by(VolunteerDispatch.sent_at.desc(), VolunteerDispatch.id.desc())
            .first()
        )

    def _apply_source_context(self, volunteer: Volunteer, source_context: VolunteerSourceContext) -> None:
        volunteer.source_user_id = source_context.source_user_id
        volunteer.source_username = source_context.source_username
        volunteer.first_name = source_context.first_name
        volunteer.last_name = source_context.last_name
        if not volunteer.display_name:
            volunteer.display_name = self._source_display_name(source_context)
        volunteer.last_seen_at = utc_now()

    def _source_display_name(self, source_context: VolunteerSourceContext) -> str | None:
        parts = [source_context.first_name, source_context.last_name]
        display_name = " ".join(part.strip() for part in parts if part and part.strip())
        return display_name or source_context.source_username