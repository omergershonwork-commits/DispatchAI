from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.dispatch import DispatchRecommendationItem, DispatchRecommendationResponse
from app.services.dispatch_matching import DispatchMatchingError, VolunteerMatchingService

router = APIRouter(prefix="/dispatch", tags=["dispatch"])
"""Router containing dispatch recommendation endpoints."""


def get_volunteer_matching_service(db: Session = Depends(get_db)) -> VolunteerMatchingService:
    """Return the volunteer matching service used by dispatch endpoints."""

    return VolunteerMatchingService(db)


@router.post(
    "/incidents/{incident_id}/recommendations",
    response_model=DispatchRecommendationResponse,
    status_code=status.HTTP_201_CREATED,
)
def recommend_volunteers_for_incident(
    incident_id: int,
    limit: int = Query(default=3, ge=1, le=10),
    matching_service: VolunteerMatchingService = Depends(get_volunteer_matching_service),
) -> DispatchRecommendationResponse:
    """Generate and persist ranked volunteer recommendations for an incident."""

    try:
        batch = matching_service.recommend_for_incident(incident_id=incident_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DispatchMatchingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="dispatch_matching_unavailable",
        ) from exc

    return DispatchRecommendationResponse(
        incident_id=batch.incident_id,
        scenario=batch.scenario,
        scenario_confidence=batch.scenario_confidence,
        recommendations=[
            DispatchRecommendationItem(
                recommendation_id=recommendation.recommendation_id,
                incident_id=recommendation.incident_id,
                volunteer_id=recommendation.volunteer_id,
                scenario=recommendation.scenario,
                rank=recommendation.rank,
                total_score=recommendation.total_score,
                score_breakdown=recommendation.score_breakdown,
            )
            for recommendation in batch.recommendations
        ],
    )
