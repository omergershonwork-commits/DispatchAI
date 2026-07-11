import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import Base
from app.models.incident import INCIDENT_STATUS_DISPATCHED, INCIDENT_STATUS_READY_FOR_DISPATCH, Incident
from app.models.volunteer import (
    DISPATCH_STATUS_ACCEPTED,
    DISPATCH_STATUS_DECLINED,
    DISPATCH_STATUS_SENT,
    VOLUNTEER_STATUS_AVAILABLE,
    VOLUNTEER_STATUS_BUSY,
    VOLUNTEER_STATUS_PENDING_RESPONSE,
    Volunteer,
    VolunteerDispatch,
)
from app.services.volunteer_management import VolunteerManagementService, VolunteerSourceContext


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = local_session()
    try:
        yield session
    finally:
        session.close()


def context(text: str) -> VolunteerSourceContext:
    return VolunteerSourceContext(
        source="telegram",
        source_chat_id=111,
        source_user_id=222,
        source_username="omer",
        first_name="Omer",
        last_name="Gershon",
        raw_text=text,
    )


def create_ready_volunteer(db: Session) -> Volunteer:
    volunteer = Volunteer(
        source="telegram",
        source_chat_id=111,
        source_user_id=222,
        source_username="omer",
        display_name="Omer Gershon",
        status=VOLUNTEER_STATUS_AVAILABLE,
        metadata_json={"registration_complete": True, "available_now": True},
    )
    db.add(volunteer)
    db.commit()
    db.refresh(volunteer)
    return volunteer


def create_incident(db: Session) -> Incident:
    incident = Incident(
        source="telegram",
        source_chat_id=999,
        raw_text="Need help",
        summary="Person needs help",
        incident_type="medical",
        location_text="Tel Aviv",
        urgency="high",
        needs=["medical help"],
        confidence=0.9,
        status=INCIDENT_STATUS_READY_FOR_DISPATCH,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def test_offer_waits_for_acceptance(db_session: Session) -> None:
    volunteer = create_ready_volunteer(db_session)
    incident = create_incident(db_session)
    service = VolunteerManagementService(db_session)

    offer = service.create_dispatch_request(volunteer.id, "Offer", incident.id)

    dispatch = db_session.get(VolunteerDispatch, offer.dispatch_id)
    db_session.refresh(volunteer)
    assert dispatch is not None
    assert dispatch.status == DISPATCH_STATUS_SENT
    assert volunteer.status == VOLUNTEER_STATUS_PENDING_RESPONSE
    assert incident.status == INCIDENT_STATUS_READY_FOR_DISPATCH


def test_accept_marks_busy_and_notifies_reporter_contract(db_session: Session) -> None:
    volunteer = create_ready_volunteer(db_session)
    incident = create_incident(db_session)
    service = VolunteerManagementService(db_session)
    offer = service.create_dispatch_request(volunteer.id, "Offer", incident.id)

    result = service.process_message(context("accept"))

    dispatch = db_session.get(VolunteerDispatch, offer.dispatch_id)
    db_session.refresh(volunteer)
    db_session.refresh(incident)
    assert dispatch is not None
    assert dispatch.status == DISPATCH_STATUS_ACCEPTED
    assert volunteer.status == VOLUNTEER_STATUS_BUSY
    assert incident.status == INCIDENT_STATUS_DISPATCHED
    assert result.dispatch_action == "accepted"
    assert result.reporter_chat_id == 999
    assert "Omer Gershon" in (result.reporter_reply_text or "")


def test_decline_releases_volunteer_and_incident(db_session: Session) -> None:
    volunteer = create_ready_volunteer(db_session)
    incident = create_incident(db_session)
    service = VolunteerManagementService(db_session)
    offer = service.create_dispatch_request(volunteer.id, "Offer", incident.id)

    result = service.process_message(context("I can't come"))

    dispatch = db_session.get(VolunteerDispatch, offer.dispatch_id)
    db_session.refresh(volunteer)
    db_session.refresh(incident)
    assert dispatch is not None
    assert dispatch.status == DISPATCH_STATUS_DECLINED
    assert volunteer.status == VOLUNTEER_STATUS_AVAILABLE
    assert incident.status == INCIDENT_STATUS_READY_FOR_DISPATCH
    assert result.dispatch_action == "declined"


def test_cancel_declines_pending_offer_instead_of_registration(db_session: Session) -> None:
    volunteer = create_ready_volunteer(db_session)
    incident = create_incident(db_session)
    service = VolunteerManagementService(db_session)
    offer = service.create_dispatch_request(volunteer.id, "Offer", incident.id)

    result = service.process_message(context("/cancel"))

    dispatch = db_session.get(VolunteerDispatch, offer.dispatch_id)
    assert dispatch is not None
    assert dispatch.status == DISPATCH_STATUS_DECLINED
    assert result.dispatch_action == "declined"
