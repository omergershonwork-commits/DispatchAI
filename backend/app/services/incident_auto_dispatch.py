import logging
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
    Volunteer,
    VolunteerDispatch,
)
from app.services.dispatch_matching import DispatchMatchingError
from app.services.geospatial_matching import GeospatialVolunteerMatchingService
from app.services.incident_assigned_forces import sync_assigned_force
from app.services.telegram_bot_client import TelegramBotClient, TelegramBotClientError
from app.services.volunteer_management import VolunteerManagementError, VolunteerManagementService

logger = logging.getLogger(__name__)


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
        self.matching_service = GeospatialVolunteerMatchingService(db)
        self.volunteer_service = VolunteerManagementService(db)

    def dispatch_ready_incident(self, incident_id: int) -> IncidentAutoDispatchResult:
        logger.info("automatic_dispatch_started incident_id=%s", incident_id)
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
            logger.info(
                "automatic_dispatch_skipped incident_id=%s reason=already_has_open_offer dispatch_id=%s volunteer_id=%s status=%s",
                incident_id,
                existing_open.id,
                existing_open.volunteer_id,
                existing_open.status,
            )
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
        logger.info(
            "automatic_dispatch_previous_offers incident_id=%s volunteer_ids=%s",
            incident_id,
            sorted(previously_offered_ids),
        )

        try:
            batch = self.matching_service.recommend_for_incident(incident_id=incident_id, limit=20)
        except (DispatchMatchingError, ValueError) as exc:
            logger.exception(
                "automatic_dispatch_matching_failed incident_id=%s error_type=%s",
                incident_id,
                type(exc).__name__,
            )
            raise IncidentAutoDispatchError("Volunteer matching failed.") from exc

        logger.info(
            "automatic_dispatch_recommendations incident_id=%s scenario=%s recommendation_count=%s",
            incident_id,
            batch.scenario,
            len(batch.recommendations),
        )
        recommendation = next(
            (
                item
                for item in batch.recommendations
                if item.volunteer_id not in previously_offered_ids
            ),
            None,
        )
        if recommendation is None:
            reason = "location_unverified" if batch.scenario == "location_unverified" else "no_available_volunteer"
            logger.warning(
                "automatic_dispatch_not_sent incident_id=%s reason=%s recommendation_count=%s",
                incident_id,
                reason,
                len(batch.recommendations),
            )
            return IncidentAutoDispatchResult(
                incident_id=incident_id,
                volunteer_id=None,
                dispatch_id=None,
                sent=False,
                reason=reason,
            )

        incident = self.db.get(Incident, incident_id)
        if incident is None:
            logger.error("automatic_dispatch_failed incident_id=%s reason=incident_missing_after_matching", incident_id)
            raise IncidentAutoDispatchError("Incident was not found after matching.")

        distance_km = recommendation.score_breakdown.get("distance_km")
        logger.info(
            "automatic_dispatch_candidate_selected incident_id=%s volunteer_id=%s recommendation_id=%s rank=%s total_score=%.6f distance_km=%s",
            incident_id,
            recommendation.volunteer_id,
            recommendation.recommendation_id,
            recommendation.rank,
            recommendation.total_score,
            distance_km,
        )
        message_text = self._build_dispatch_message(incident, distance_km)
        try:
            dispatch = self.volunteer_service.create_dispatch_request(
                volunteer_id=recommendation.volunteer_id,
                message_text=message_text,
                incident_id=incident.id,
            )
            self.telegram_bot_client.send_message(dispatch.source_chat_id, dispatch.message_text)

            volunteer = self.db.get(Volunteer, recommendation.volunteer_id)
            sync_assigned_force(
                incident,
                volunteer,
                status="pending_response",
                dispatch_id=dispatch.dispatch_id,
                distance_km=distance_km,
            )

            recommendation_row = self.db.get(DispatchRecommendation, recommendation.recommendation_id)
            if recommendation_row is not None:
                recommendation_row.status = RECOMMENDATION_STATUS_DISPATCH_CREATED
            self.db.commit()
        except (VolunteerManagementError, TelegramBotClientError, SQLAlchemyError, ValueError) as exc:
            self.db.rollback()
            logger.exception(
                "automatic_dispatch_notification_failed incident_id=%s volunteer_id=%s error_type=%s",
                incident_id,
                recommendation.volunteer_id,
                type(exc).__name__,
            )
            raise IncidentAutoDispatchError("Volunteer notification failed.") from exc

        logger.info(
            "automatic_dispatch_offer_sent incident_id=%s volunteer_id=%s dispatch_id=%s chat_id=%s distance_km=%s",
            incident.id,
            recommendation.volunteer_id,
            dispatch.dispatch_id,
            dispatch.source_chat_id,
            distance_km,
        )
        return IncidentAutoDispatchResult(
            incident_id=incident.id,
            volunteer_id=recommendation.volunteer_id,
            dispatch_id=dispatch.dispatch_id,
            sent=True,
            reason="offer_sent",
        )

    def _build_dispatch_message(self, incident: Incident, distance_km: float | None = None) -> str:
        needs = ", ".join(incident.needs or []) or "general assistance"
        affected = incident.casualties_text or "not specified"
        distance_line = f"Estimated distance: {float(distance_km):.1f} km\n" if distance_km is not None else ""
        return (
            "New volunteer dispatch offer\n"
            f"Title: {incident.title or incident.incident_type or 'Incident'}\n"
            f"Location: {incident.location_text or 'unknown'}\n"
            f"{distance_line}"
            f"Summary: {incident.summary}\n"
            f"Urgency: {incident.urgency}\n"
            f"Affected people: {affected}\n"
            f"Needs: {needs}\n\n"
            "Reply accept if you can respond, or decline if you cannot. "
            "You will not receive another offer while this response is pending."
        )
