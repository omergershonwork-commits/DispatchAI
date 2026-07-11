from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.incident import INCIDENT_STATUS_READY_FOR_DISPATCH, Incident
from app.models.volunteer import (
    DISPATCH_STATUS_ACCEPTED,
    DISPATCH_STATUS_EXPIRED,
    DISPATCH_STATUS_SENT,
    VOLUNTEER_STATUS_AVAILABLE,
    Volunteer,
    VolunteerDispatch,
)
from app.services.incident_assigned_forces import sync_assigned_force
from app.services.incident_auto_dispatch import IncidentAutoDispatchError, IncidentAutoDispatchService
from app.services.telegram_bot_client import TelegramBotClient, TelegramBotClientError
from app.services.volunteer_management import VolunteerCommandResult, VolunteerSourceContext

EN_ROUTE_COMMANDS = {"en route", "en_route", "/enroute", "/en_route", "on the way", "on my way"}
ARRIVED_COMMANDS = {"arrived", "/arrived", "i arrived", "im here", "i'm here"}


class DispatchLifecycleError(RuntimeError):
    """Raised when dispatch timeout or progress processing fails."""


@dataclass(frozen=True)
class DispatchTimeoutRunResult:
    expired_count: int
    replacement_offer_count: int
    exhausted_incident_count: int


class DispatchLifecycleService:
    """Manage accepted-dispatch progress and unanswered-offer expiration."""

    def __init__(
        self,
        db: Session,
        volunteer_bot_client: TelegramBotClient | None = None,
        incident_bot_client: TelegramBotClient | None = None,
        offer_timeout_seconds: int = 120,
    ) -> None:
        if offer_timeout_seconds <= 0:
            raise ValueError("Offer timeout must be positive.")
        self.db = db
        self.volunteer_bot_client = volunteer_bot_client
        self.incident_bot_client = incident_bot_client
        self.offer_timeout = timedelta(seconds=offer_timeout_seconds)

    def process_progress_message(
        self,
        source_context: VolunteerSourceContext,
    ) -> VolunteerCommandResult | None:
        normalized = " ".join(source_context.raw_text.strip().lower().split())
        action = None
        if normalized in EN_ROUTE_COMMANDS:
            action = "en_route"
        elif normalized in ARRIVED_COMMANDS:
            action = "arrived"
        if action is None:
            return None

        try:
            volunteer = (
                self.db.query(Volunteer)
                .filter(
                    Volunteer.source == source_context.source,
                    Volunteer.source_chat_id == source_context.source_chat_id,
                )
                .first()
            )
            if volunteer is None:
                return VolunteerCommandResult(None, None, None, "You are not registered yet.")

            dispatch = (
                self.db.query(VolunteerDispatch)
                .filter(
                    VolunteerDispatch.volunteer_id == volunteer.id,
                    VolunteerDispatch.status == DISPATCH_STATUS_ACCEPTED,
                )
                .order_by(VolunteerDispatch.sent_at.desc(), VolunteerDispatch.id.desc())
                .first()
            )
            if dispatch is None:
                return VolunteerCommandResult(
                    volunteer.id,
                    volunteer.status,
                    None,
                    "No accepted assignment is active right now.",
                )

            metadata = dict(dispatch.metadata_json or {})
            timestamp_key = "en_route_at" if action == "en_route" else "arrived_at"
            metadata[timestamp_key] = datetime.now(UTC).isoformat()
            metadata["progress"] = action
            dispatch.metadata_json = metadata

            incident = self.db.get(Incident, dispatch.incident_id) if dispatch.incident_id else None
            sync_assigned_force(
                incident,
                volunteer,
                status=action,
                dispatch_id=dispatch.id,
            )
            self.db.commit()

            display_name = volunteer.display_name or volunteer.source_username or f"Volunteer {volunteer.id}"
            if action == "en_route":
                volunteer_reply = "Status updated: you are en route. Reply arrived when you reach the location."
                reporter_reply = f"Volunteer {display_name} is on the way to your location."
            else:
                volunteer_reply = "Status updated: you arrived. Reply done when the assignment is complete."
                reporter_reply = f"Volunteer {display_name} reported arrival at your location."

            return VolunteerCommandResult(
                volunteer.id,
                volunteer.status,
                dispatch.id,
                volunteer_reply,
                incident_id=dispatch.incident_id,
                dispatch_action=action,
                reporter_source=incident.source if incident else None,
                reporter_chat_id=incident.source_chat_id if incident else None,
                reporter_reply_text=reporter_reply if incident else None,
            )
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise DispatchLifecycleError("Dispatch progress update failed.") from exc

    def reporter_update_for_result(
        self,
        result: VolunteerCommandResult,
    ) -> tuple[int, str] | None:
        if result.dispatch_action != "done" or result.incident_id is None:
            return None
        incident = self.db.get(Incident, result.incident_id)
        if incident is None or incident.source != "telegram":
            return None
        return (
            incident.source_chat_id,
            "The volunteer marked the assignment complete. Please send a new message if more help is still needed.",
        )

    def expire_unanswered_offers(self) -> DispatchTimeoutRunResult:
        cutoff = datetime.now(UTC) - self.offer_timeout
        try:
            offers = (
                self.db.query(VolunteerDispatch)
                .filter(
                    VolunteerDispatch.status == DISPATCH_STATUS_SENT,
                    VolunteerDispatch.sent_at <= cutoff,
                )
                .order_by(VolunteerDispatch.sent_at.asc(), VolunteerDispatch.id.asc())
                .all()
            )
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise DispatchLifecycleError("Dispatch timeout lookup failed.") from exc

        replacement_count = 0
        exhausted_count = 0
        for dispatch in offers:
            try:
                volunteer = self.db.get(Volunteer, dispatch.volunteer_id)
                dispatch.status = DISPATCH_STATUS_EXPIRED
                metadata = dict(dispatch.metadata_json or {})
                metadata["expired_at"] = datetime.now(UTC).isoformat()
                dispatch.metadata_json = metadata
                if volunteer is not None:
                    volunteer.status = VOLUNTEER_STATUS_AVAILABLE

                incident = self.db.get(Incident, dispatch.incident_id) if dispatch.incident_id else None
                if incident is not None:
                    incident.status = INCIDENT_STATUS_READY_FOR_DISPATCH
                    sync_assigned_force(
                        incident,
                        volunteer,
                        status="expired",
                        dispatch_id=dispatch.id,
                    )
                self.db.commit()

                if volunteer is not None and self.volunteer_bot_client is not None:
                    try:
                        self.volunteer_bot_client.send_message(
                            volunteer.source_chat_id,
                            "The dispatch offer expired because no response was received. You are available for other offers.",
                        )
                    except (TelegramBotClientError, ValueError):
                        pass

                if incident is None or self.volunteer_bot_client is None:
                    continue
                dispatcher = IncidentAutoDispatchService(self.db, self.volunteer_bot_client)
                result = dispatcher.dispatch_ready_incident(incident.id)
                if result.sent:
                    replacement_count += 1
                elif result.reason == "no_available_volunteer":
                    exhausted_count += 1
                    self._notify_no_volunteer(incident)
            except (SQLAlchemyError, IncidentAutoDispatchError) as exc:
                self.db.rollback()
                raise DispatchLifecycleError("Dispatch timeout processing failed.") from exc

        return DispatchTimeoutRunResult(
            expired_count=len(offers),
            replacement_offer_count=replacement_count,
            exhausted_incident_count=exhausted_count,
        )

    def _notify_no_volunteer(self, incident: Incident) -> None:
        if incident.source != "telegram" or self.incident_bot_client is None:
            return
        metadata = dict(incident.metadata_json or {})
        if metadata.get("no_volunteer_notified"):
            return
        try:
            self.incident_bot_client.send_message(
                incident.source_chat_id,
                "No registered volunteer has accepted yet. Your report remains saved. If there is immediate danger, contact local emergency services now.",
            )
            metadata["no_volunteer_notified"] = True
            metadata["no_volunteer_notified_at"] = datetime.now(UTC).isoformat()
            incident.metadata_json = metadata
            self.db.commit()
        except (TelegramBotClientError, ValueError, SQLAlchemyError):
            self.db.rollback()
