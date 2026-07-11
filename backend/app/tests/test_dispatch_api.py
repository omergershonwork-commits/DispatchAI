from fastapi.testclient import TestClient

from app.api.dispatch import get_volunteer_matching_service
from app.main import app
from app.services.dispatch_matching import (
    DispatchMatchingError,
    DispatchRecommendationBatch,
    DispatchRecommendationResult,
)

client = TestClient(app)


class FakeVolunteerMatchingService:
    """Test double for dispatch recommendation endpoint tests."""

    def __init__(
        self,
        result: DispatchRecommendationBatch | None = None,
        error: Exception | None = None,
    ) -> None:
        """Create a fake matching service."""

        self.result = result
        self.error = error
        self.calls: list[tuple[int, int]] = []

    def recommend_for_incident(self, incident_id: int, limit: int = 3) -> DispatchRecommendationBatch:
        """Record a recommendation request and return or raise the fake outcome."""

        self.calls.append((incident_id, limit))
        if self.error:
            raise self.error
        if self.result is None:
            raise AssertionError("Fake matching result was not configured.")
        return self.result


def recommendation_batch() -> DispatchRecommendationBatch:
    """Return a fake persisted recommendation batch."""

    return DispatchRecommendationBatch(
        incident_id=7,
        scenario="medical_urgent",
        scenario_confidence=0.85,
        recommendations=[
            DispatchRecommendationResult(
                recommendation_id=100,
                incident_id=7,
                volunteer_id=44,
                scenario="medical_urgent",
                rank=1,
                total_score=0.91,
                score_breakdown={
                    "location": 1.0,
                    "availability": 1.0,
                    "skill_match": 0.8,
                    "response_time": 0.9,
                    "reliability": 0.95,
                },
            )
        ],
    )


def override_matching_service(fake_service: FakeVolunteerMatchingService) -> None:
    """Install a FastAPI dependency override for the matching service."""

    app.dependency_overrides[get_volunteer_matching_service] = lambda: fake_service


def clear_dependency_overrides() -> None:
    """Clear FastAPI dependency overrides after endpoint tests."""

    app.dependency_overrides.clear()


def test_recommend_volunteers_endpoint_returns_persisted_recommendations() -> None:
    """Verify dispatch endpoint returns ranked volunteer recommendations."""

    fake_service = FakeVolunteerMatchingService(result=recommendation_batch())
    override_matching_service(fake_service)

    try:
        response = client.post("/dispatch/incidents/7/recommendations?limit=3")
    finally:
        clear_dependency_overrides()

    assert response.status_code == 201
    assert response.json() == {
        "incident_id": 7,
        "scenario": "medical_urgent",
        "scenario_confidence": 0.85,
        "recommendations": [
            {
                "recommendation_id": 100,
                "incident_id": 7,
                "volunteer_id": 44,
                "scenario": "medical_urgent",
                "rank": 1,
                "total_score": 0.91,
                "score_breakdown": {
                    "location": 1.0,
                    "availability": 1.0,
                    "skill_match": 0.8,
                    "response_time": 0.9,
                    "reliability": 0.95,
                },
            }
        ],
    }
    assert fake_service.calls == [(7, 3)]


def test_recommend_volunteers_endpoint_returns_400_for_invalid_state() -> None:
    """Verify domain validation errors return HTTP 400."""

    fake_service = FakeVolunteerMatchingService(error=ValueError("Incident is not ready."))
    override_matching_service(fake_service)

    try:
        response = client.post("/dispatch/incidents/7/recommendations")
    finally:
        clear_dependency_overrides()

    assert response.status_code == 400
    assert response.json() == {"detail": "Incident is not ready."}


def test_recommend_volunteers_endpoint_returns_503_for_matching_errors() -> None:
    """Verify infrastructure matching errors return safe HTTP 503 detail."""

    fake_service = FakeVolunteerMatchingService(error=DispatchMatchingError("db unavailable"))
    override_matching_service(fake_service)

    try:
        response = client.post("/dispatch/incidents/7/recommendations")
    finally:
        clear_dependency_overrides()

    assert response.status_code == 503
    assert response.json() == {"detail": "dispatch_matching_unavailable"}


def test_recommend_volunteers_endpoint_rejects_invalid_limit() -> None:
    """Verify FastAPI validates the recommendation limit query parameter."""

    response = client.post("/dispatch/incidents/7/recommendations?limit=0")

    assert response.status_code == 422
