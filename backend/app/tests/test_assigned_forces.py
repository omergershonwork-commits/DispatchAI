from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.volunteer_telegram import sync_volunteer_dashboard_state
from app.db.session import Base
from app.models.incident import INCIDENT_STATUS_DISPATCHED, Incident
from app.models.volunteer import VOLUNTEER_STATUS_BUSY, Volunteer
from app.services.incident_assigned_forces import sync_assigned_force
from app.services.volunteer_management import VolunteerCommandResult


def test_assigned_force_upsert_reuses_volunteer_entry() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        incident = Incident(
            source="telegram",
            source_chat_id=1,
            raw_text="report",
            title="Road accident",
            summary="Road accident report",
            incident_type="medical",
            location_text="Main Street",
            urgency="high",
            casualties_text="Two people affected",
            needs=["medical"],
            confidence=0.9,
            status=INCIDENT_STATUS_DISPATCHED,
            metadata_json={},
        )
        volunteer = Volunteer(
            source="telegram",
            source_chat_id=2,
            display_name="Mordehai",
            status=VOLUNTEER_STATUS_BUSY,
            trust_score=0.5,
            inventory=[],
            metadata_json={"registration_complete": True, "distance_text": "2 km"},
        )
        db.add_all([incident, volunteer])
        db.commit()

        sync_assigned_force(incident, volunteer, "pending_response", dispatch_id=10)
        sync_assigned_force(incident, volunteer, "en_route", dispatch_id=10)
        db.commit()

        assigned = incident.metadata_json["assigned_forces"]
        assert len(assigned) == 1
        assert assigned[0]["volunteer_id"] == volunteer.id
        assert assigned[0]["status"] == "en_route"
        assert assigned[0]["distance"] == "2 km"
    finally:
        db.close()


def test_done_updates_assigned_force_and_trust_score() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        incident = Incident(
            source="telegram",
            source_chat_id=1,
            raw_text="report",
            title="Supply request",
            summary="Supply request report",
            incident_type="food",
            location_text="Main Street",
            urgency="medium",
            casualties_text=None,
            needs=["food"],
            confidence=0.8,
            status=INCIDENT_STATUS_DISPATCHED,
            metadata_json={},
        )
        volunteer = Volunteer(
            source="telegram",
            source_chat_id=2,
            display_name="Mordehai",
            status=VOLUNTEER_STATUS_BUSY,
            trust_score=0.5,
            inventory=[],
            metadata_json={"registration_complete": True, "phone_number": "0500000000"},
        )
        db.add_all([incident, volunteer])
        db.commit()

        result = VolunteerCommandResult(
            volunteer_id=volunteer.id,
            volunteer_status="available",
            dispatch_id=11,
            reply_text="done",
            incident_id=incident.id,
            dispatch_action="done",
        )
        sync_volunteer_dashboard_state(db, result)

        db.refresh(volunteer)
        db.refresh(incident)
        assert volunteer.trust_score == 0.52
        assert volunteer.phone_number == "0500000000"
        assert incident.metadata_json["assigned_forces"][0]["status"] == "done"
    finally:
        db.close()
