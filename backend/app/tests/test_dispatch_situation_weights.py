import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import Base
from app.models.incident import INCIDENT_STATUS_READY_FOR_DISPATCH, Incident
from app.models.volunteer import VOLUNTEER_STATUS_AVAILABLE, Volunteer
from app.services.dispatch_matching import ScenarioSelectionService, VolunteerMatchingService


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = local()
    try:
        yield session
    finally:
        session.close()


def create_incident(
    db: Session,
    summary: str,
    incident_type: str,
    urgency: str,
    needs: list[str],
) -> Incident:
    incident = Incident(
        source="telegram",
        source_chat_id=100,
        raw_text=summary,
        title="Situation report",
        summary=summary,
        incident_type=incident_type,
        location_text="Tel Aviv",
        urgency=urgency,
        casualties_text=None,
        needs=needs,
        confidence=0.9,
        status=INCIDENT_STATUS_READY_FOR_DISPATCH,
        metadata_json={},
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def create_volunteer(
    db: Session,
    chat_id: int,
    *,
    skills: list[str],
    vehicle: str,
    inventory: list[str],
    response_time_minutes: float,
    trust_score: float = 0.8,
    gender: str | None = None,
    height_cm: float | None = None,
    weight_kg: float | None = None,
) -> Volunteer:
    volunteer = Volunteer(
        source="telegram",
        source_chat_id=chat_id,
        display_name=f"Volunteer {chat_id}",
        status=VOLUNTEER_STATUS_AVAILABLE,
        trust_score=trust_score,
        inventory=inventory,
        gender=gender,
        height_cm=height_cm,
        weight_kg=weight_kg,
        metadata_json={
            "registration_complete": True,
            "service_areas": ["Tel Aviv"],
            "skills": skills,
            "vehicle": vehicle,
            "response_time_minutes": response_time_minutes,
            "max_distance_km": 30,
            "distance_km": 5,
        },
    )
    db.add(volunteer)
    db.commit()
    db.refresh(volunteer)
    return volunteer


def test_all_situation_weights_are_normalized() -> None:
    selector = ScenarioSelectionService()

    assert "evacuation_shelter" in selector.scenarios
    for scenario in selector.scenarios.values():
        assert sum(scenario.weights.values()) == pytest.approx(1.0)
        assert set(scenario.weights) == {
            "location",
            "skill_match",
            "response_time",
            "reliability",
            "inventory_match",
            "vehicle_match",
        }


def test_critical_urgency_increases_response_and_location_weights(db_session: Session) -> None:
    service = VolunteerMatchingService(db_session)
    scenario = service.scenario_service.scenarios["medical_urgent"]

    medium_weights = service._effective_weights(scenario, "medium")
    critical_weights = service._effective_weights(scenario, "critical")

    assert sum(critical_weights.values()) == pytest.approx(1.0)
    assert critical_weights["response_time"] > medium_weights["response_time"]
    assert critical_weights["location"] > medium_weights["location"]


def test_transport_scenario_prioritizes_matching_vehicle(db_session: Session) -> None:
    incident = create_incident(
        db_session,
        summary="Transport pickup and delivery needed",
        incident_type="transport",
        urgency="high",
        needs=["transport", "pickup", "delivery"],
    )
    vehicle_volunteer = create_volunteer(
        db_session,
        201,
        skills=["driver", "transport"],
        vehicle="van",
        inventory=[],
        response_time_minutes=20,
    )
    create_volunteer(
        db_session,
        202,
        skills=["driver", "transport"],
        vehicle="none",
        inventory=[],
        response_time_minutes=2,
    )

    result = VolunteerMatchingService(db_session).recommend_for_incident(incident.id, limit=2)

    assert result.scenario == "transport"
    assert result.recommendations[0].volunteer_id == vehicle_volunteer.id
    assert result.recommendations[0].score_breakdown["weight_vehicle_match"] > 0.35
    assert result.recommendations[0].score_breakdown["vehicle_match"] == 1.0


def test_supplies_scenario_prioritizes_matching_inventory(db_session: Session) -> None:
    incident = create_incident(
        db_session,
        summary="Food water and blanket supplies needed",
        incident_type="food",
        urgency="medium",
        needs=["food", "water", "blanket"],
    )
    equipped = create_volunteer(
        db_session,
        301,
        skills=["logistics"],
        vehicle="car",
        inventory=["food", "water", "blanket"],
        response_time_minutes=20,
    )
    create_volunteer(
        db_session,
        302,
        skills=["logistics"],
        vehicle="car",
        inventory=[],
        response_time_minutes=5,
    )

    result = VolunteerMatchingService(db_session).recommend_for_incident(incident.id, limit=2)

    assert result.scenario == "supplies"
    assert result.recommendations[0].volunteer_id == equipped.id
    assert result.recommendations[0].score_breakdown["inventory_match"] == 1.0
    assert result.recommendations[0].score_breakdown["weight_inventory_match"] > 0.29


def test_biodata_does_not_change_matching_score(db_session: Session) -> None:
    incident = create_incident(
        db_session,
        summary="General help and support needed",
        incident_type="other",
        urgency="medium",
        needs=["help", "support"],
    )
    first = create_volunteer(
        db_session,
        401,
        skills=["support"],
        vehicle="car",
        inventory=["water"],
        response_time_minutes=10,
        gender="male",
        height_cm=190,
        weight_kg=95,
    )
    second = create_volunteer(
        db_session,
        402,
        skills=["support"],
        vehicle="car",
        inventory=["water"],
        response_time_minutes=10,
        gender="female",
        height_cm=155,
        weight_kg=50,
    )

    service = VolunteerMatchingService(db_session)
    scenario = service.scenario_service.select_for_incident(incident).scenario
    first_score = service._score_volunteer(incident, first, scenario)
    second_score = service._score_volunteer(incident, second, scenario)

    assert first_score.total_score == second_score.total_score
    assert first_score.breakdown == second_score.breakdown
