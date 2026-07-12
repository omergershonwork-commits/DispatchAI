import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.dispatch_recommendation import DispatchRecommendation
from app.models.incident import Incident
from app.models.volunteer import Volunteer
from app.services.dispatch_matching import (
    DispatchRecommendationBatch,
    DispatchRecommendationResult,
    VolunteerMatchingService,
)
from app.services.geocoding import GeoPoint, haversine_distance_km

logger = logging.getLogger(__name__)


class GeospatialVolunteerMatchingService(VolunteerMatchingService):
    """Filter and rerank recommendations using verified coordinates."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def recommend_for_incident(
        self,
        incident_id: int,
        limit: int = 3,
    ) -> DispatchRecommendationBatch:
        if not settings.geocoding_enabled:
            logger.info(
                "geospatial_matching_disabled incident_id=%s fallback=text_matching",
                incident_id,
            )
            return super().recommend_for_incident(incident_id=incident_id, limit=limit)

        incident = self.db.get(Incident, incident_id)
        if incident is None:
            logger.warning("geospatial_matching_failed incident_id=%s reason=incident_not_found", incident_id)
            raise ValueError("Incident was not found.")

        if incident.latitude is None or incident.longitude is None:
            logger.warning(
                "geospatial_matching_blocked incident_id=%s reason=incident_coordinates_missing location_text=%r",
                incident_id,
                incident.location_text,
            )
            self._remove_recommendations(incident_id)
            return DispatchRecommendationBatch(
                incident_id=incident.id,
                scenario="location_unverified",
                scenario_confidence=0.0,
                recommendations=[],
            )

        logger.info(
            "geospatial_matching_started incident_id=%s latitude=%.6f longitude=%.6f location_source=%s limit=%s",
            incident_id,
            incident.latitude,
            incident.longitude,
            incident.location_source or "unknown",
            limit,
        )
        base_batch = super().recommend_for_incident(incident_id=incident_id, limit=100)
        incident_point = GeoPoint(incident.latitude, incident.longitude, source=incident.location_source or "stored")
        eligible: list[tuple[DispatchRecommendationResult, float, float]] = []

        for recommendation in base_batch.recommendations:
            volunteer = self.db.get(Volunteer, recommendation.volunteer_id)
            if volunteer is None:
                logger.warning(
                    "volunteer_excluded incident_id=%s volunteer_id=%s reason=volunteer_not_found",
                    incident_id,
                    recommendation.volunteer_id,
                )
                continue
            if volunteer.latitude is None or volunteer.longitude is None:
                logger.info(
                    "volunteer_excluded incident_id=%s volunteer_id=%s reason=coordinates_missing",
                    incident_id,
                    volunteer.id,
                )
                continue

            volunteer_point = GeoPoint(
                volunteer.latitude,
                volunteer.longitude,
                source=volunteer.location_source or "stored",
            )
            distance_km = haversine_distance_km(incident_point, volunteer_point)
            max_distance = self._max_distance_km(volunteer)
            if max_distance is None:
                logger.info(
                    "volunteer_excluded incident_id=%s volunteer_id=%s reason=max_distance_missing distance_km=%.3f",
                    incident_id,
                    volunteer.id,
                    distance_km,
                )
                continue
            if max_distance <= 0:
                logger.info(
                    "volunteer_excluded incident_id=%s volunteer_id=%s reason=invalid_max_distance max_distance_km=%.3f",
                    incident_id,
                    volunteer.id,
                    max_distance,
                )
                continue
            if distance_km > max_distance:
                logger.info(
                    "volunteer_excluded incident_id=%s volunteer_id=%s reason=outside_travel_radius distance_km=%.3f max_distance_km=%.3f",
                    incident_id,
                    volunteer.id,
                    distance_km,
                    max_distance,
                )
                continue

            distance_score = max(0.0, 1.0 - (distance_km / max_distance))
            location_weight = float(recommendation.score_breakdown.get("weight_location", 0.0))
            previous_location = float(recommendation.score_breakdown.get("location", 0.0))
            adjusted_total = (
                recommendation.total_score
                - previous_location * location_weight
                + distance_score * location_weight
            )
            logger.info(
                "volunteer_eligible incident_id=%s volunteer_id=%s distance_km=%.3f max_distance_km=%.3f base_score=%.6f adjusted_score=%.6f",
                incident_id,
                volunteer.id,
                distance_km,
                max_distance,
                recommendation.total_score,
                adjusted_total,
            )
            eligible.append((recommendation, distance_km, adjusted_total))

        eligible.sort(key=lambda item: (item[2], -item[1]), reverse=True)
        selected = eligible[:limit]
        selected_ids = {item[0].recommendation_id for item in selected}

        query = self.db.query(DispatchRecommendation).filter(
            DispatchRecommendation.incident_id == incident_id
        )
        if selected_ids:
            query = query.filter(~DispatchRecommendation.id.in_(selected_ids))
        query.delete(synchronize_session=False)

        results: list[DispatchRecommendationResult] = []
        for rank, (recommendation, distance_km, adjusted_total) in enumerate(selected, start=1):
            row = self.db.get(DispatchRecommendation, recommendation.recommendation_id)
            if row is None:
                continue
            breakdown = dict(recommendation.score_breakdown)
            max_distance = self._max_distance_km(self.db.get(Volunteer, recommendation.volunteer_id))
            breakdown["distance_km"] = round(distance_km, 3)
            breakdown["max_distance_km"] = round(float(max_distance or 0), 3)
            breakdown["location"] = round(max(0.0, 1.0 - distance_km / float(max_distance)), 6)
            row.rank = rank
            row.total_score = round(adjusted_total, 6)
            row.score_breakdown = breakdown
            results.append(
                DispatchRecommendationResult(
                    recommendation_id=row.id,
                    incident_id=incident_id,
                    volunteer_id=row.volunteer_id,
                    scenario=row.scenario,
                    rank=rank,
                    total_score=row.total_score,
                    score_breakdown=breakdown,
                )
            )
            logger.info(
                "volunteer_ranked incident_id=%s volunteer_id=%s rank=%s total_score=%.6f distance_km=%.3f",
                incident_id,
                row.volunteer_id,
                rank,
                row.total_score,
                distance_km,
            )

        self.db.commit()
        logger.info(
            "geospatial_matching_completed incident_id=%s base_candidates=%s eligible_candidates=%s selected_candidates=%s",
            incident_id,
            len(base_batch.recommendations),
            len(eligible),
            len(results),
        )
        return DispatchRecommendationBatch(
            incident_id=base_batch.incident_id,
            scenario=base_batch.scenario,
            scenario_confidence=base_batch.scenario_confidence,
            recommendations=results,
        )

    def _remove_recommendations(self, incident_id: int) -> None:
        removed = self.db.query(DispatchRecommendation).filter(
            DispatchRecommendation.incident_id == incident_id
        ).delete(synchronize_session=False)
        self.db.commit()
        logger.info("dispatch_recommendations_removed incident_id=%s removed=%s", incident_id, removed)

    def _max_distance_km(self, volunteer: Volunteer | None) -> float | None:
        if volunteer is None:
            return None
        value = (volunteer.metadata_json or {}).get("max_distance_km")
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
