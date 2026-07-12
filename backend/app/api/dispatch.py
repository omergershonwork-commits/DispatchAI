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


@router.get(
    "/incidents/{incident_id}/recommendations",
    response_model=list[DispatchRecommendationItem],
)
def get_recommendations_for_incident(
    incident_id: int,
    db: Session = Depends(get_db),
) -> list[DispatchRecommendationItem]:
    """Get the existing volunteer recommendations for an incident."""
    from app.models.dispatch_recommendation import DispatchRecommendation, RECOMMENDATION_STATUS_RECOMMENDED
    
    recs = db.query(DispatchRecommendation).filter(
        DispatchRecommendation.incident_id == incident_id,
        DispatchRecommendation.status == RECOMMENDATION_STATUS_RECOMMENDED
    ).order_by(DispatchRecommendation.rank.asc()).all()
    
    return [
        DispatchRecommendationItem(
            recommendation_id=rec.id,
            incident_id=rec.incident_id,
            volunteer_id=rec.volunteer_id,
            scenario=rec.scenario,
            rank=rec.rank,
            total_score=rec.total_score,
            score_breakdown=rec.score_breakdown,
        )
        for rec in recs
    ]
