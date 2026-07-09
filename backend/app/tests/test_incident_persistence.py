import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import Base
from app.models.incident import (
    INCIDENT_STATUS_PENDING_DETAILS,
    INCIDENT_STATUS_READY_FOR_DISPATCH,
    Incident,
)
from app.schemas.incident import IncidentExtractionResult
from app.schemas.telegram import TelegramWebhookUpdate
from app.services.incident_persistence import IncidentPersistenceService


@pytest.fixture
def db_session() -> Session:
    """Create an isolated in-memory database session for persistence tests."""

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


def telegram_update(
    update_id: int = 123456,
    message_id: int = 42,
    chat_id: int = 987654321,
    text: str = "I need medical help near Dizengoff Center",
) -> TelegramWebhookUpdate:
    """Return a validated Telegram webhook update for persistence tests."""

    return TelegramWebhookUpdate.model_validate(
        {
            "update_id": update_id,
            "message": {
                "message_id": message_id,
                "date": 1_725_000_000,
                "chat": {
                    "id": chat_id,
                    "type": "private",
                    "first_name": "Omer",
                },
                "from": {
                    "id": 111222333,
                    "is_bot": False,
                    "first_name": "Omer",
                    "username": "omer_user",
                },
                "text": text,
            },
        }
    )


def actionable_extraction_result() -> IncidentExtractionResult:
    """Return an actionable extraction result for persistence tests."""

    return IncidentExtractionResult(
        is_incident=True,
        summary="Person needs medical help near Dizengoff Center.",
        incident_type="medical",
        location_text="Dizengoff Center",
        urgency="high",
        people_count=1,
        contact_name="Omer",
        phone_number="0501234567",
        needs=["medical help"],
        confidence=0.91,
        missing_fields=[],
        follow_up_question=None,
        should_create_incident=True,
        should_ask_follow_up=False,
        rejection_reason=None,
    )


def pending_extraction_result() -> IncidentExtractionResult:
    """Return an extraction result that needs more sender details."""

    return IncidentExtractionResult(
        is_incident=True,
        summary="Person needs help.",
        incident_type="medical",
        location_text=None,
        urgency="medium",
        people_count=None,
        contact_name=None,
        phone_number=None,
        needs=["medical help"],
        confidence=0.55,
        missing_fields=["location_text"],
        follow_up_question="Where exactly is help needed?",
        should_create_incident=False,
        should_ask_follow_up=True,
        rejection_reason=None,
    )


def non_incident_extraction_result() -> IncidentExtractionResult:
    """Return a non-incident extraction result that must not be persisted."""

    return IncidentExtractionResult(
        is_incident=False,
        summary="Greeting only.",
        incident_type=None,
        location_text=None,
        urgency="unknown",
        people_count=None,
        contact_name=None,
        phone_number=None,
        needs=[],
        confidence=0.7,
        missing_fields=[],
        follow_up_question=None,
        should_create_incident=False,
        should_ask_follow_up=False,
        rejection_reason="Not an incident.",
    )


def test_persist_from_telegram_creates_ready_incident(db_session: Session) -> None:
    """Verify actionable extraction creates a ready incident row."""

    service = IncidentPersistenceService(db_session)

    result = service.persist_from_telegram(
        telegram_update(),
        actionable_extraction_result(),
        "I need medical help near Dizengoff Center",
    )

    assert result is not None
    assert result.created is True
    assert result.updated is False
    assert result.status == INCIDENT_STATUS_READY_FOR_DISPATCH

    incident = db_session.get(Incident, result.incident_id)
    assert incident is not None
    assert incident.status == INCIDENT_STATUS_READY_FOR_DISPATCH
    assert incident.source == "telegram"
    assert incident.source_chat_id == 987654321
    assert incident.source_message_id == 42
    assert incident.summary == "Person needs medical help near Dizengoff Center."
    assert incident.location_text == "Dizengoff Center"
    assert incident.needs == ["medical help"]


def test_persist_from_telegram_creates_pending_incident(db_session: Session) -> None:
    """Verify incomplete extraction creates a pending incident row."""

    service = IncidentPersistenceService(db_session)

    result = service.persist_from_telegram(
        telegram_update(),
        pending_extraction_result(),
        "I need medical help",
    )

    assert result is not None
    assert result.created is True
    assert result.updated is False
    assert result.status == INCIDENT_STATUS_PENDING_DETAILS

    incident = db_session.get(Incident, result.incident_id)
    assert incident is not None
    assert incident.status == INCIDENT_STATUS_PENDING_DETAILS
    assert incident.location_text is None
    assert incident.metadata_json["follow_up_question"] == "Where exactly is help needed?"


def test_persist_from_telegram_updates_existing_pending_incident(db_session: Session) -> None:
    """Verify follow-up details from the same chat update the pending incident."""

    service = IncidentPersistenceService(db_session)
    first_result = service.persist_from_telegram(
        telegram_update(text="I need medical help"),
        pending_extraction_result(),
        "I need medical help",
    )

    second_result = service.persist_from_telegram(
        telegram_update(
            update_id=123457,
            message_id=43,
            text="The location is Dizengoff Center",
        ),
        actionable_extraction_result(),
        "The location is Dizengoff Center",
    )

    assert first_result is not None
    assert second_result is not None
    assert second_result.incident_id == first_result.incident_id
    assert second_result.created is False
    assert second_result.updated is True
    assert second_result.status == INCIDENT_STATUS_READY_FOR_DISPATCH

    incident = db_session.get(Incident, second_result.incident_id)
    assert incident is not None
    assert incident.status == INCIDENT_STATUS_READY_FOR_DISPATCH
    assert incident.location_text == "Dizengoff Center"
    assert incident.source_message_id == 43
    assert "--- follow-up ---" in incident.raw_text


def test_persist_from_telegram_does_not_create_for_non_incident(db_session: Session) -> None:
    """Verify non-incident extractions are not persisted."""

    service = IncidentPersistenceService(db_session)

    result = service.persist_from_telegram(
        telegram_update(text="hello"),
        non_incident_extraction_result(),
        "hello",
    )

    assert result is None
    assert db_session.query(Incident).count() == 0


def test_persist_from_telegram_does_not_create_for_none_extraction(db_session: Session) -> None:
    """Verify missing extraction output is not persisted."""

    service = IncidentPersistenceService(db_session)

    result = service.persist_from_telegram(
        telegram_update(text="hello"),
        None,
        "hello",
    )

    assert result is None
    assert db_session.query(Incident).count() == 0
