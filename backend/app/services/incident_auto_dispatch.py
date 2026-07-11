from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.dispatch_recommendation import (
    RECOMMENDATION_STATUS_DISPATCH_CREATED,
    DispatchRecommendation,
)
from app.models.incident import INCIDENT_STATUS_DISPATCHED, Incident
from app.models.volunteer import DISPATCH_STATUS_SENT, VolunteerDispatch
from app.services.dispatch_matching import DispatchMatchingError, VolunteerMatchingService
from app.services.telegram_bot_client import TelegramBotClient, TelegramBotClientError
from app.services.volunteer_management import VolunteerManagementError, VolunteerManagementService


class IncidentAutoDispatchError(RuntimeError):
    """Raised when automatic volunteer notification cannot be completed."""


@dataclass(frozen=True)
class IncidentAutoDispatchResult:
    """Result of attempting to notify a matched volunteer."""

    incident_id: int
    volunteer_id: int | None
    dispatch_id: int | None
    sent: bool
    reason: str


class IncidentAutoDispatchService:
    """Match a ready incident and notify the highest-ranked available volunteer."""

    def __init__(self, db: Session, telegram_bot_client: TelegramBotClient) -> None:
        self.db = db
        self.telegram_bot_client = telegram_bot_client
        self.matching_service = VolunteerMatchingService(db)
        self.volunteer_service = VolunteerManagementService(db)

    def dispatch_ready_incident(self, incident_id: int) -> IncidentAutoDispatchResult:
        """Send one dispatch request for a ready incident, without duplicating active requests."""

        existing = (
            self.db.query(VolunteerDispatch)
            .filter(
                VolunteerDispatch.incident_id == incident_id,
                VolunteerDispatch.status == DISPATCH_STATUS_SENT,
            )
            .order_by(VolunteerDispatch.id.desc())
            .first()
        )
        if existing is not None:
            return IncidentAutoDispatchResult(
                incident_id=incident_id,
                volunteer_id=existing.volunteer_id,
                dispatch_id=existing.id,
                sent=False,
                reason="already_dispatched",
            )

        try:
            batch = self.matching_service.recommend_for_incident(incident_id=incident_id, limit=1)
        except (DispatchMatchingError, ValueError) as exc:
            raise IncidentAutoDispatchError("Volunteer matching failed.") from exc

        if not batch.recommendations:
            return IncidentAutoDispatchResult(
                incident_id=incident_id,
                volunteer_id=None,
                dispatch_id=None,
                sent=False,
                reason="no_available_volunteer",
            )

        recommendation = batch.recommendations[0]
        incident = self.db.get(Incident, incident_id)
        if incident is None:
            raise IncidentAutoDispatchError("Incident was not found after matching.")

        message_text = self._build_dispatch_message(incident)
        try:
            dispatch = self.volunteer_service.create_dispatch_request(
                volunteer_id=recommendation.volunteer_id,
                message_text=message_text,
                incident_id=incident.id,
            )
            self.telegram_bot_client.send_message(dispatch.source_chat_id, dispatch.message_text)
            recommendation_row = self.db.get(DispatchRecommendation, recommendation.recommendation_id)
            if recommendation_row is not None:
                recommendation_row.status = RECOMMENDATION_STATUS_DISPATCH_CREATED
            incident.status = INCIDENT_STATUS_DISPATCHED
            self.db.commit()
        except (VolunteerManagementError, TelegramBotClientError, SQLAlchemyError, ValueError) as exc:
            self.db.rollback()
            raise IncidentAutoDispatchError("Volunteer notification failed.") from exc

        return IncidentAutoDispatchResult(
            incident_id=incident.id,
            volunteer_id=recommendation.volunteer_id,
            dispatch_id=dispatch.dispatch_id,
            sent=True,
            reason="sent",
        )

    def _build_dispatch_message(self, incident: Incident) -> str:
        """Build a concise volunteer assignment message from persisted incident data."""

        needs = ", ".join(incident.needs or []) or "general assistance"
        return (
            "New volunteer dispatch request\n"
            f"Location: {incident.location_text or 'unknown'}\n"
            f"Summary: {incident.summary}\n"
            f"Urgency: {incident.urgency}\n"
            f"Needs: {needs}\n"
            "Reply done when the assignment is completed."
        )
