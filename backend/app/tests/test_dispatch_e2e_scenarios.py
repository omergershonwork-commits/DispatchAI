from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import Base
from app.models.dispatch_recommendation import DispatchRecommendation
from app.models.incident import INCIDENT_STATUS_READY_FOR_DISPATCH, Incident
from app.models.volunteer import (
    DISPATCH_STATUS_SENT,
    VOLUNTEER_STATUS_AVAILABLE,
    VOLUNTEER_STATUS_BUSY,
    VOLUNTEER_STATUS_INACTIVE,
    VOLUNTEER_STATUS_PENDING_RESPONSE,
    Volunteer,
    VolunteerDispatch,
)
from app.services import geospatial_matching
from app.services.incident_auto_dispatch import IncidentAutoDispatchService


@dataclass(frozen=True)
class Profile:
    skills: tuple[str, ...]
    inventory: tuple[str, ...]
    vehicle: str


@dataclass(frozen=True)
class ScenarioCase:
    case_id: str
    summary: str
    incident_type: str
    urgency: str
    needs: tuple[str, ...]
    expected_scenario: str
    profile: Profile
    blocked_status: str | None = None
    blocked_out_of_range: bool = False


PROFILES = {
    "medical": Profile(
        ("paramedic", "medical", "first_aid"),
        ("medical_kit", "aed"),
        "ambulance",
    ),
    "fire": Profile(
        ("fire_response", "rescue", "evacuation"),
        ("fire_extinguisher", "protective_gear", "helmet"),
        "fire_truck",
    ),
    "rescue": Profile(
        ("search_and_rescue", "rescue", "medical"),
        ("rescue_kit", "rope", "helmet", "flashlight"),
        "four_wheel_drive",
    ),
    "security": Profile(
        ("security", "crisis_support", "coordination"),
        ("radio", "flashlight", "first_aid_kit"),
        "motorcycle",
    ),
    "evacuation": Profile(
        ("evacuation", "shelter", "transport", "logistics"),
        ("blanket", "water", "food", "radio"),
        "bus",
    ),
    "transport": Profile(
        ("driver", "transport", "delivery"),
        ("water", "phone_charger"),
        "van",
    ),
    "supplies": Profile(
        ("logistics", "supplies", "delivery"),
        ("food", "water", "medicine", "blanket", "charger"),
        "van",
    ),
    "general": Profile(
        ("support", "coordination"),
        ("water",),
        "car",
    ),
}


CASES = [
    ScenarioCase(
        "medical-inactive-best-is-skipped",
        "Medical injury requires doctor ambulance and first aid",
        "medical",
        "critical",
        ("medical", "first_aid"),
        "medical_urgent",
        PROFILES["medical"],
        blocked_status=VOLUNTEER_STATUS_INACTIVE,
    ),
    ScenarioCase(
        "fire-out-of-range-best-is-skipped",
        "Building fire smoke flames rescue evacuation",
        "fire",
        "critical",
        ("fire_response", "rescue"),
        "fire_response",
        PROFILES["fire"],
        blocked_out_of_range=True,
    ),
    ScenarioCase(
        "rescue-busy-best-is-skipped",
        "Earthquake collapse trapped rescue search debris",
        "rescue",
        "critical",
        ("search_and_rescue", "rescue"),
        "disaster_rescue",
        PROFILES["rescue"],
        blocked_status=VOLUNTEER_STATUS_BUSY,
    ),
    ScenarioCase(
        "security-pending-best-is-skipped",
        "Security threat robbery unsafe crisis support",
        "security",
        "high",
        ("security", "crisis_support"),
        "security_urgent",
        PROFILES["security"],
        blocked_status=VOLUNTEER_STATUS_PENDING_RESPONSE,
    ),
    ScenarioCase(
        "evacuation-inactive-best-is-skipped",
        "Evacuation shelter displaced residents transport",
        "evacuation",
        "high",
        ("evacuation", "shelter", "transport"),
        "evacuation_shelter",
        PROFILES["evacuation"],
        blocked_status=VOLUNTEER_STATUS_INACTIVE,
    ),
    ScenarioCase(
        "transport-busy-best-is-skipped",
        "Transport pickup drive delivery vehicle",
        "transport",
        "high",
        ("transport", "pickup", "delivery"),
        "transport",
        PROFILES["transport"],
        blocked_status=VOLUNTEER_STATUS_BUSY,
    ),
    ScenarioCase(
        "supplies-pending-best-is-skipped",
        "Food water medicine supplies blanket delivery",
        "supplies",
        "medium",
        ("food", "water", "medicine"),
        "supplies",
        PROFILES["supplies"],
        blocked_status=VOLUNTEER_STATUS_PENDING_RESPONSE,
    ),
    ScenarioCase(
        "general-inactive-best-is-skipped",
        "Urgent help support assistance general problem",
        "other",
        "medium",
        ("help", "support"),
        "general_assistance",
        PROFILES["general"],
        blocked_status=VOLUNTEER_STATUS_INACTIVE,
    ),
    ScenarioCase(
        "medical-out-of-range-best-is-skipped",
        "Medical emergency injured person first aid ambulance",
        "medical",
        "high",
        ("medical", "first_aid"),
        "medical_urgent",
        PROFILES["medical"],
        blocked_out_of_range=True,
    ),
    ScenarioCase(
        "fire-busy-best-is-skipped",
        "Fire smoke burning flames rescue",
        "fire",
        "high",
        ("fire_response", "rescue"),
        "fire_response",
        PROFILES["fire"],
        blocked_status=VOLUNTEER_STATUS_BUSY,
    ),
    ScenarioCase(
        "transport-pending-best-is-skipped",
        "Vehicle transport ride pickup delivery",
        "transport",
        "medium",
        ("transport", "delivery"),
        "transport",
        PROFILES["transport"],
        blocked_status=VOLUNTEER_STATUS_PENDING_RESPONSE,
    ),
    ScenarioCase(
        "supplies-inactive-best-is-skipped",
        "Equipment food water supplies charger delivery",
        "supplies",
        "low",
        ("food", "water", "supplies"),
        "supplies",
        PROFILES["supplies"],
        blocked_status=VOLUNTEER_STATUS_INACTIVE,
    ),
]


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class RecordingBot:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str]] = []

    def send_message(self, chat_id: int, text: str) -> object:
        self.sent_messages.append((chat_id, text))
        return object()


def add_incident(db: Session, case: ScenarioCase) -> Incident:
    incident = Incident(
        source="telegram",
        source_chat_id=700001,
        raw_text=case.summary,
        title=case.case_id,
        summary=case.summary,
        incident_type=case.incident_type,
        location_text="Scenario location",
        latitude=32.0,
        longitude=35.0,
        location_source="telegram_gps",
        urgency=case.urgency,
        casualties_text="Reported people need assistance",
        needs=list(case.needs),
        confidence=0.95,
        status=INCIDENT_STATUS_READY_FOR_DISPATCH,
        metadata_json={"assigned_forces": []},
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def add_volunteer(
    db: Session,
    *,
    chat_id: int,
    name: str,
    profile: Profile,
    status: str,
    latitude: float,
    max_distance_km: float,
    response_minutes: float,
    trust_score: float,
) -> Volunteer:
    volunteer = Volunteer(
        source="telegram",
        source_chat_id=chat_id,
        display_name=name,
        latitude=latitude,
        longitude=35.0,
        location_source="telegram_gps",
        location_updated_at=datetime.now(UTC),
        status=status,
        trust_score=trust_score,
        inventory=list(profile.inventory),
        metadata_json={
            "registration_complete": True,
            "available_now": status == VOLUNTEER_STATUS_AVAILABLE,
            "service_areas": ["Scenario location"],
            "skills": list(profile.skills),
            "vehicle": profile.vehicle,
            "response_time_minutes": response_minutes,
            "max_distance_km": max_distance_km,
        },
    )
    db.add(volunteer)
    db.commit()
    db.refresh(volunteer)
    return volunteer


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_dispatch_selects_best_eligible_volunteer(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    case: ScenarioCase,
) -> None:
    monkeypatch.setattr(
        geospatial_matching,
        "settings",
        SimpleNamespace(geocoding_enabled=True),
    )
    incident = add_incident(db_session, case)

    selected = add_volunteer(
        db_session,
        chat_id=710001,
        name="Selected eligible volunteer",
        profile=case.profile,
        status=VOLUNTEER_STATUS_AVAILABLE,
        latitude=32.03,
        max_distance_km=100,
        response_minutes=7,
        trust_score=0.9,
    )

    blocked_status = case.blocked_status or VOLUNTEER_STATUS_AVAILABLE
    blocked_latitude = 33.0 if case.blocked_out_of_range else 32.001
    blocked_max_distance = 20 if case.blocked_out_of_range else 100
    blocked = add_volunteer(
        db_session,
        chat_id=710002,
        name="Blocked stronger volunteer",
        profile=case.profile,
        status=blocked_status,
        latitude=blocked_latitude,
        max_distance_km=blocked_max_distance,
        response_minutes=1,
        trust_score=0.99,
    )

    generic = add_volunteer(
        db_session,
        chat_id=710003,
        name="Generic nearby volunteer",
        profile=Profile(("support",), (), "none"),
        status=VOLUNTEER_STATUS_AVAILABLE,
        latitude=32.005,
        max_distance_km=100,
        response_minutes=3,
        trust_score=0.65,
    )

    original_blocked_status = blocked.status
    original_generic_status = generic.status
    bot = RecordingBot()
    result = IncidentAutoDispatchService(db_session, bot).dispatch_ready_incident(incident.id)

    assert result.sent is True
    assert result.reason == "offer_sent"
    assert result.volunteer_id == selected.id
    assert result.dispatch_id is not None
    assert bot.sent_messages == [(selected.source_chat_id, bot.sent_messages[0][1])]
    assert "Estimated distance:" in bot.sent_messages[0][1]

    dispatch = db_session.get(VolunteerDispatch, result.dispatch_id)
    assert dispatch is not None
    assert dispatch.volunteer_id == selected.id
    assert dispatch.status == DISPATCH_STATUS_SENT

    recommendation = (
        db_session.query(DispatchRecommendation)
        .filter(
            DispatchRecommendation.incident_id == incident.id,
            DispatchRecommendation.volunteer_id == selected.id,
        )
        .one()
    )
    assert recommendation.scenario == case.expected_scenario
    assert recommendation.rank == 1
    assert recommendation.score_breakdown["distance_km"] <= 100

    db_session.refresh(selected)
    db_session.refresh(blocked)
    db_session.refresh(generic)
    assert selected.status == VOLUNTEER_STATUS_PENDING_RESPONSE
    assert blocked.status == original_blocked_status
    assert generic.status == original_generic_status


def test_dispatch_sends_no_offer_when_all_volunteers_are_ineligible(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        geospatial_matching,
        "settings",
        SimpleNamespace(geocoding_enabled=True),
    )
    case = CASES[0]
    incident = add_incident(db_session, case)
    add_volunteer(
        db_session,
        chat_id=720001,
        name="Inactive volunteer",
        profile=case.profile,
        status=VOLUNTEER_STATUS_INACTIVE,
        latitude=32.001,
        max_distance_km=100,
        response_minutes=1,
        trust_score=0.99,
    )
    add_volunteer(
        db_session,
        chat_id=720002,
        name="Busy volunteer",
        profile=case.profile,
        status=VOLUNTEER_STATUS_BUSY,
        latitude=32.002,
        max_distance_km=100,
        response_minutes=1,
        trust_score=0.99,
    )
    add_volunteer(
        db_session,
        chat_id=720003,
        name="Out of range volunteer",
        profile=case.profile,
        status=VOLUNTEER_STATUS_AVAILABLE,
        latitude=33.0,
        max_distance_km=10,
        response_minutes=1,
        trust_score=0.99,
    )

    bot = RecordingBot()
    result = IncidentAutoDispatchService(db_session, bot).dispatch_ready_incident(incident.id)

    assert result.sent is False
    assert result.reason == "no_available_volunteer"
    assert result.volunteer_id is None
    assert bot.sent_messages == []
    assert db_session.query(VolunteerDispatch).count() == 0
