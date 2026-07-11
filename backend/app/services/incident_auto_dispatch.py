from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.dispatch_recommendation import (
    RECOMMENDATION_STATUS_DISPATCH_CREATED,
    DispatchRecommendation,
)
from app.models.incident import Incident
from app.models.volunteer import (
    DISPATCH_STATUS_ACCEPTED,
    DISPATCH_STATUS_SENT,
    VolunteerDispatch,
)
from app.services.dispatch_matching import DispatchMatchingError, VolunteerMatchingService
from app.services.telegram_bot_client import TelegramBotClient, TelegramBotClientError
from app.services.volunteer_management import VolunteerManagementError, VolunteerManagementService


class IncidentAutoDispatchError(RuntimeError):
    """Raised when automatic volunteer notification cannot be completed."""


@dataclass(frozen=True)
class IncidentAutoDispatchResult:
    incident_id: int
    volunteer_id: int | None
    dispatch_id: int | None
    sent: bool
    reason: str


class IncidentAutoDispatchService:
    """Match a ready incident and send an offer to the next eligible volunteer."""

    def __init__(self, db: Session, telegram_bot_client: TelegramBotClient) -> None:
        self.db = db
        self.telegram_bot_client = telegram_bot_client
        self.matching_service = VolunteerMatchingService(db)
        self.volunteer_service = VolunteerManagementService(db)

    def dispatch_ready_incident(self, incident_id: int) -> IncidentAutoDispatchResult:
        """Send one offer without duplicating an open offer or accepted assignment."""

        existing_open = (
            self.db.query(VolunteerDispatch)
            .filter(
                VolunteerDispatch.incident_id == incident_id,
                VolunteerDispatch.status.in_([DISPATCH_STATUS_SENT, DISPATCH_STATUS_ACCEPTED]),
            )
            .order_by(VolunteerDispatch.id.desc())
            .first()
        )
        if existing_open is not None:
            return IncidentAutoDispatchResult(
                incident_id=incident_id,
                volunteer_id=existing_open.volunteer_id,
                dispatch_id=existing_open.id,
                sent=False,
                reason="already_has_open_offer",
            )

        previously_offered_ids = {
            row[0]
            for row in self.db.query(VolunteerDispatch.volunteer_id)
            .filter(VolunteerDispatch.incident_id == incident_id)
            .all()
        }

        try:
            batch = self.matching_service.recommend_for_incident(incident_id=incident_id, limit=20)
        except (DispatchMatchingError, ValueError) as exc:
            raise IncidentAutoDispatchError("Volunteer matching failed.") from exc

        recommendation = next(
            (
                item
                for item in batch.recommendations
                if item.volunteer_id not in previously_offered_ids
            ),
            None,
        )
        if recommendation is None:
            return IncidentAutoDispatchResult(
                incident_id=incident_id,
                volunteer_id=None,
                dispatch_id=None,
                sent=False,
                reason="no_available_volunteer",
            )

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
            self.db.commit()
        except (VolunteerManagementError, TelegramBotClientError, SQLAlchemyError, ValueError) as exc:
            self.db.rollback()
            raise IncidentAutoDispatchError("Volunteer notification failed.") from exc

        return IncidentAutoDispatchResult(
            incident_id=incident.id,
            volunteer_id=recommendation.volunteer_id,
            dispatch_id=dispatch.dispatch_id,
            sent=True,
            reason="offer_sent",
        )

    def _build_dispatch_message(self, incident: Incident) -> str:
        needs = ", ".join(incident.needs or []) or "general assistance"
        return (
            "New volunteer dispatch offer\n"
            f"Location: {incident.location_text or 'unknown'}\n"
            f"Summary: {incident.summary}\n"
            f"Urgency: {incident.urgency}\n"
            f"Needs: {needs}\n\n"
            "Reply accept if you can respond, or decline if you cannot. "
            "You will not receive another offer while this response is pending."
        )