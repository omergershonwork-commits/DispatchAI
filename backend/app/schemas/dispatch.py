from pydantic import BaseModel, Field


class DispatchRecommendationItem(BaseModel):
    """One persisted volunteer recommendation for an incident."""

    recommendation_id: int = Field(description="Persisted recommendation identifier.")
    incident_id: int = Field(description="Incident being matched.")
    volunteer_id: int = Field(description="Recommended volunteer identifier.")
    scenario: str = Field(description="Scenario used for scoring.")
    rank: int = Field(description="One-based recommendation rank.")
    total_score: float = Field(description="Final weighted score from zero to one.")
    score_breakdown: dict[str, float] = Field(description="Per-dimension score breakdown.")


class DispatchRecommendationResponse(BaseModel):
    """Response returned after generating volunteer recommendations."""

    incident_id: int = Field(description="Incident that was matched.")
    scenario: str = Field(description="Selected dispatch scenario.")
    scenario_confidence: float = Field(description="Scenario selection confidence from zero to one.")
    recommendations: list[DispatchRecommendationItem] = Field(
        description="Persisted top volunteer recommendations ordered by rank."
    )
