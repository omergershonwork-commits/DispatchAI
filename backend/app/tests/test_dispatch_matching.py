import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import Base
from app.models.dispatch_recommendation import DispatchRecommendation
from app.models.incident import INCIDENT_STATUS_PENDING_DETAILS, INCIDENT_STATUS_READY_FOR_DISPATCH, Incident
from app.models.volunteer import VOLUNTEER_STATUS_AVAILABLE, VOLUNTEER_STATUS_BUSY, Volunteer
from app.services.dispatch_matching import ScenarioSelectionService, VolunteerMatchingService


@pytest.fixture
def db_session() -> Session:
    """Create an isolated in-memory database session for dispatch matching tests."""

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


def create_incident(
    db_session: Session,
    status: str = INCIDENT_STATUS_READY_FOR_DISPATCH,
    summary: str = "Two injured people need medical help near Dizengoff Center.",
    incident_type: str = "medical",
    location_text: str = "Dizengoff Center",
    urgency: str = "high",
    needs: list[str] | None = None,
) -> Incident:
    """Persist an incident for matching tests."""

    incident = Incident(
        source="telegram",
        source_chat_id=123,
        raw_text=summary,
        summary=summary,
        incident_type=incident_type,
        location_text=location_text,
        urgency=urgency,
        people_count=2,
        needs=needs or ["medical help"],
        confidence=0.9,
        status=status,
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)
    return incident


def create_volunteer(
    db_session: Session,
    status: str = VOLUNTEER_STATUS_AVAILABLE,
    skills: list[str] | None = None,
    service_areas: list[str] | None = None,
    response_time_minutes: int | None = 10,
    reliability_score: float = 0.8,
) -> Volunteer:
    """Persist a volunteer candidate for matching tests."""

    volunteer = Volunteer(
        source="telegram",
        source_chat_id=10_000 + db_session.query(Volunteer).count(),
        source_user_id=20_000 + db_session.query(Volunteer).count(),
        display_name="Volunteer",
        status=status,
        metadata_json={
            "skills": skills or [],
            "service_areas": service_areas or [],
            "response_time_minutes": response_time_minutes,
            "reliability_score": reliability_score,
        },
    )
    db_session.add(volunteer)
    db_session.commit()
    db_session.refresh(volunteer)
    return volunteer


def test_scenario_selection_picks_medical_urgent(db_session: Session) -> None:
    """Verify urgent medical incidents select the medical scenario."""

    incident = create_incident(db_session)
    selector = ScenarioSelectionService()

    selection = selector.select_for_incident(incident)

    assert selection.scenario.name == "medical_urgent"
    assert selection.confidence >= 0.7
    assert "medical" in selection.matched_terms


def test_scenario_selection_falls_back_to_general_assistance(db_session: Session) -> None:
    """Verify unclear incidents fall back to the general scenario."""

    incident = create_incident(
        db_session,
        summary="Someone needs help near the park.",
        incident_type="unknown",
        location_text="Park",
        urgency="unknown",
        needs=["help"],
    )
    selector = ScenarioSelectionService()

    selection = selector.select_for_incident(incident)

    assert selection.scenario.name == "general_assistance"


def test_recommend_for_incident_persists_top_ranked_volunteers(db_session: Session) -> None:
    """Verify matching persists ranked volunteer recommendations."""

    incident = create_incident(db_session)
    medical_volunteer = create_volunteer(
        db_session,
        skills=["medical", "first_aid"],
        service_areas=["Dizengoff Center"],
        response_time_minutes=8,
        reliability_score=0.9,
    )
    create_volunteer(
        db_session,
        skills=["driver"],
        service_areas=["Dizengoff Center"],
        response_time_minutes=4,
        reliability_score=0.8,
    )
    create_volunteer(
        db_session,
        status=VOLUNTEER_STATUS_BUSY,
        skills=["medical"],
        service_areas=["Dizengoff Center"],
        response_time_minutes=2,
        reliability_score=1.0,
    )

    service = VolunteerMatchingService(db_session)
    result = service.recommend_for_incident(incident.id, limit=2)

    assert result.incident_id == incident.id
    assert result.scenario == "medical_urgent"
    assert len(result.recommendations) == 2
    assert result.recommendations[0].volunteer_id == medical_volunteer.id
    assert result.recommendations[0].rank == 1
    assert result.recommendations[0].total_score > result.recommendations[1].total_score
    assert db_session.query(DispatchRecommendation).count() == 2


def test_recommend_for_incident_replaces_existing_recommendations(db_session: Session) -> None:
    """Verify re-running matching replaces old recommendation rows."""

    incident = create_incident(db_session)
    create_volunteer(
        db_session,
        skills=["medical"],
        service_areas=["Dizengoff Center"],
        response_time_minutes=12,
    )
    service = VolunteerMatchingService(db_session)

    first_result = service.recommend_for_incident(incident.id, limit=1)
    second_result = service.recommend_for_incident(incident.id, limit=1)

    assert len(first_result.recommendations) == 1
    assert len(second_result.recommendations) == 1
    assert first_result.recommendations[0].recommendation_id != second_result.recommendations[0].recommendation_id
    assert db_session.query(DispatchRecommendation).count() == 1


def test_recommend_for_incident_returns_empty_when_no_available_volunteers(db_session: Session) -> None:
    """Verify matching can safely return an empty recommendation list."""

    incident = create_incident(db_session)
    create_volunteer(
        db_session,
        status=VOLUNTEER_STATUS_BUSY,
        skills=["medical"],
        service_areas=["Dizengoff Center"],
    )
    service = VolunteerMatchingService(db_session)

    result = service.recommend_for_incident(incident.id, limit=3)

    assert result.recommendations == []
    assert db_session.query(DispatchRecommendation).count() == 0


def test_recommend_for_incident_rejects_pending_incident(db_session: Session) -> None:
    """Verify pending incidents cannot be matched yet."""

    incident = create_incident(db_session, status=INCIDENT_STATUS_PENDING_DETAILS)
    service = VolunteerMatchingService(db_session)

    with pytest.raises(ValueError, match="not ready"):
        service.recommend_for_incident(incident.id)


def test_recommend_for_incident_rejects_missing_incident(db_session: Session) -> None:
    """Verify missing incident ids fail clearly."""

    service = VolunteerMatchingService(db_session)

    with pytest.raises(ValueError, match="not found"):
        service.recommend_for_incident(9999)
