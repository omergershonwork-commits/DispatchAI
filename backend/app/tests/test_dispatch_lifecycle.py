from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import Base
from app.models.incident import INCIDENT_STATUS_READY_FOR_DISPATCH, Incident
from app.models.volunteer import (
    DISPATCH_STATUS_ACCEPTED,
    DISPATCH_STATUS_EXPIRED,
    DISPATCH_STATUS_SENT,
    VOLUNTEER_STATUS_AVAILABLE,
    VOLUNTEER_STATUS_PENDING_RESPONSE,
    Volunteer,
    VolunteerDispatch,
)
from app.services.dispatch_lifecycle import DispatchLifecycleService
from app.services.volunteer_management import VolunteerSourceContext


class FakeTelegramClient:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    def send_message(self, chat_id: int, text: str) -> object:
        self.messages.append((chat_id, text))
        return object()


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


def create_incident(db: Session, chat_id: int = 500) -> Incident:
    incident = Incident(
        source="telegram",
        source_update_id=1,
        source_message_id=1,
        source_chat_id=chat_id,
        raw_text="Medical help needed in Tel Aviv",
        summary="Person needs medical assistance.",
        incident_type="medical",
        location_text="Tel Aviv",
        urgency="high",
        people_count=1,
        needs=["medical assistance"],
        confidence=0.95,
        status=INCIDENT_STATUS_READY_FOR_DISPATCH,
        metadata_json={},
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def create_volunteer(db: Session, chat_id: int, status: str = VOLUNTEER_STATUS_AVAILABLE) -> Volunteer:
    volunteer = Volunteer(
        source="telegram",
        source_chat_id=chat_id,
        display_name=f"Volunteer {chat_id}",
        status=status,
        metadata_json={
            "registration_complete": True,
            "available_now": True,
            "service_areas": ["Tel Aviv"],
            "skills": ["medical", "rescue"],
        },
    )
    db.add(volunteer)
    db.commit()
    db.refresh(volunteer)
    return volunteer


def test_expired_offer_moves_to_next_volunteer(db_session: Session) -> None:
    incident = create_incident(db_session)
    first = create_volunteer(db_session, 101, VOLUNTEER_STATUS_PENDING_RESPONSE)
    second = create_volunteer(db_session, 202)
    old_offer = VolunteerDispatch(
        volunteer_id=first.id,
        incident_id=incident.id,
        message_text="Old offer",
        status=DISPATCH_STATUS_SENT,
        sent_at=datetime.now(UTC) - timedelta(minutes=5),
        metadata_json={},
    )
    db_session.add(old_offer)
    db_session.commit()

    volunteer_bot = FakeTelegramClient()
    incident_bot = FakeTelegramClient()
    service = DispatchLifecycleService(
        db_session,
        volunteer_bot_client=volunteer_bot,
        incident_bot_client=incident_bot,
        offer_timeout_seconds=120,
    )

    result = service.expire_unanswered_offers()

    db_session.refresh(first)
    db_session.refresh(second)
    db_session.refresh(old_offer)
    assert result.expired_count == 1
    assert result.replacement_offer_count == 1
    assert old_offer.status == DISPATCH_STATUS_EXPIRED
    assert first.status == VOLUNTEER_STATUS_AVAILABLE
    assert second.status == VOLUNTEER_STATUS_PENDING_RESPONSE
    replacement = (
        db_session.query(VolunteerDispatch)
        .filter(VolunteerDispatch.volunteer_id == second.id)
        .one()
    )
    assert replacement.status == DISPATCH_STATUS_SENT
    assert replacement.incident_id == incident.id
    assert any(chat_id == second.source_chat_id for chat_id, _ in volunteer_bot.messages)


def test_progress_updates_dispatch_and_reporter(db_session: Session) -> None:
    incident = create_incident(db_session, chat_id=700)
    volunteer = create_volunteer(db_session, 303)
    dispatch = VolunteerDispatch(
        volunteer_id=volunteer.id,
        incident_id=incident.id,
        message_text="Accepted assignment",
        status=DISPATCH_STATUS_ACCEPTED,
        metadata_json={},
    )
    db_session.add(dispatch)
    db_session.commit()

    service = DispatchLifecycleService(db_session)
    context = VolunteerSourceContext(
        source="telegram",
        source_chat_id=303,
        source_user_id=303,
        source_username="volunteer303",
        first_name="Test",
        last_name="Volunteer",
        raw_text="en route",
    )

    result = service.process_progress_message(context)

    db_session.refresh(dispatch)
    assert result is not None
    assert result.dispatch_action == "en_route"
    assert result.reporter_chat_id == 700
    assert "on the way" in (result.reporter_reply_text or "")
    assert dispatch.metadata_json["progress"] == "en_route"
    assert "en_route_at" in dispatch.metadata_json


def test_no_volunteer_notifies_reporter_after_timeout(db_session: Session) -> None:
    incident = create_incident(db_session, chat_id=900)
    volunteer = create_volunteer(db_session, 404, VOLUNTEER_STATUS_PENDING_RESPONSE)
    offer = VolunteerDispatch(
        volunteer_id=volunteer.id,
        incident_id=incident.id,
        message_text="Only offer",
        status=DISPATCH_STATUS_SENT,
        sent_at=datetime.now(UTC) - timedelta(minutes=5),
        metadata_json={},
    )
    db_session.add(offer)
    db_session.commit()

    volunteer_bot = FakeTelegramClient()
    incident_bot = FakeTelegramClient()
    service = DispatchLifecycleService(
        db_session,
        volunteer_bot_client=volunteer_bot,
        incident_bot_client=incident_bot,
        offer_timeout_seconds=120,
    )

    result = service.expire_unanswered_offers()

    assert result.exhausted_incident_count == 1
    assert incident_bot.messages
    assert incident_bot.messages[0][0] == 900
    assert "No registered volunteer" in incident_bot.messages[0][1]
