from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models.incident import INCIDENT_STATUS_DISPATCHED, Incident
from app.models.volunteer import (
    DISPATCH_STATUS_DECLINED,
    DISPATCH_STATUS_DONE,
    DISPATCH_STATUS_EXPIRED,
    VOLUNTEER_STATUS_AVAILABLE,
    Volunteer,
    VolunteerDispatch,
)


@pytest.fixture
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> TestClient:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def seed_dashboard_data(db: Session) -> tuple[Incident, Volunteer]:
    now = datetime.now(UTC)
    incident = Incident(
        source="telegram",
        source_chat_id=123,
        raw_text="report",
        title="Building fire",
        summary="A building fire was reported on the second floor.",
        incident_type="fire",
        location_text="Central Street 10",
        urgency="critical",
        casualties_text="Two people require assistance",
        needs=["rescue", "medical assistance"],
        confidence=0.94,
        contact_name="Reporter",
        phone_number="0500000000",
        status=INCIDENT_STATUS_DISPATCHED,
        metadata_json={
            "assigned_forces": [
                {
                    "volunteer_id": 1,
                    "name": "Mordehai",
                    "status": "en_route",
                    "distance": "2 km",
                    "dispatch_id": 10,
                    "updated_at": now.isoformat(),
                }
            ]
        },
    )
    volunteer = Volunteer(
        source="telegram",
        source_chat_id=456,
        source_username="mordehai_user",
        display_name="Mordehai",
        phone_number="0520000000",
        gender="male",
        height_cm=178,
        weight_kg=78,
        trust_score=0.82,
        inventory=["first aid kit", "flashlight"],
        status=VOLUNTEER_STATUS_AVAILABLE,
        metadata_json={
            "registration_complete": True,
            "skills": ["medical", "rescue"],
            "service_areas": ["Tel Aviv"],
            "vehicle": "car",
            "max_distance_km": 25,
        },
    )
    db.add_all([incident, volunteer])
    db.flush()
    db.add_all(
        [
            VolunteerDispatch(
                volunteer_id=volunteer.id,
                incident_id=incident.id,
                message_text="one",
                status=DISPATCH_STATUS_DONE,
                completed_at=now,
            ),
            VolunteerDispatch(
                volunteer_id=volunteer.id,
                incident_id=incident.id,
                message_text="two",
                status=DISPATCH_STATUS_DECLINED,
            ),
            VolunteerDispatch(
                volunteer_id=volunteer.id,
                incident_id=incident.id,
                message_text="three",
                status=DISPATCH_STATUS_EXPIRED,
            ),
        ]
    )
    db.commit()
    db.refresh(incident)
    db.refresh(volunteer)
    return incident, volunteer


def test_incident_dashboard_exposes_new_fields(client: TestClient, db_session: Session) -> None:
    incident, _ = seed_dashboard_data(db_session)

    response = client.get(f"/dashboard/incidents/{incident.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Building fire"
    assert payload["casualties_text"] == "Two people require assistance"
    assert payload["confidence"] == 0.94
    assert payload["phone_number"] == "0500000000"
    assert payload["assigned_forces"][0]["status"] == "en_route"
    assert payload["assigned_forces"][0]["distance"] == "2 km"


def test_volunteer_dashboard_exposes_biodata_and_stats(client: TestClient, db_session: Session) -> None:
    _, volunteer = seed_dashboard_data(db_session)

    response = client.get(f"/dashboard/volunteers/{volunteer.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["username"] == "mordehai_user"
    assert payload["phone_number"] == "0520000000"
    assert payload["gender"] == "male"
    assert payload["height_cm"] == 178
    assert payload["weight_kg"] == 78
    assert payload["trust_score"] == 0.82
    assert payload["inventory"] == ["first aid kit", "flashlight"]
    assert payload["completed_dispatches"] == 1
    assert payload["declined_dispatches"] == 1
    assert payload["expired_offers"] == 1
    assert payload["last_seen_at"] is not None


def test_dashboard_can_update_optional_volunteer_profile(client: TestClient, db_session: Session) -> None:
    _, volunteer = seed_dashboard_data(db_session)

    response = client.patch(
        f"/dashboard/volunteers/{volunteer.id}",
        json={
            "gender": "other",
            "height_cm": 180,
            "weight_kg": 80,
            "trust_score": 0.9,
            "inventory": ["radio", "radio", "water"],
            "phone_number": "0530000000",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["gender"] == "other"
    assert payload["height_cm"] == 180
    assert payload["weight_kg"] == 80
    assert payload["trust_score"] == 0.9
    assert payload["inventory"] == ["radio", "water"]
    assert payload["phone_number"] == "0530000000"
