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
from app.services.incident_persistence import IncidentPersistenceService, SourceIncidentContext


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


def source_context(
    source: str = "telegram",
    update_id: int = 123456,
    message_id: int = 42,
    chat_id: int = 987654321,
    raw_text: str = "I need medical help near Dizengoff Center",
) -> SourceIncidentContext:
    """Return generic source metadata for persistence tests."""

    return SourceIncidentContext(
        source=source,
        source_update_id=update_id,
        source_message_id=message_id,
        source_chat_id=chat_id,
        raw_text=raw_text,
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


def test_persist_incident_creates_ready_incident(db_session: Session) -> None:
    """Verify actionable extraction creates a ready incident row."""

    service = IncidentPersistenceService(db_session)

    result = service.persist_incident(
        source_context(),
        actionable_extraction_result(),
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


def test_persist_incident_creates_pending_incident(db_session: Session) -> None:
    """Verify incomplete extraction creates a pending incident row."""

    service = IncidentPersistenceService(db_session)

    result = service.persist_incident(
        source_context(raw_text="I need medical help"),
        pending_extraction_result(),
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


def test_persist_incident_updates_existing_pending_incident(db_session: Session) -> None:
    """Verify follow-up details from the same source chat update the pending incident."""

    service = IncidentPersistenceService(db_session)
    first_result = service.persist_incident(
        source_context(raw_text="I need medical help"),
        pending_extraction_result(),
    )

    second_result = service.persist_incident(
        source_context(
            update_id=123457,
            message_id=43,
            raw_text="The location is Dizengoff Center",
        ),
        actionable_extraction_result(),
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


def test_persist_incident_keeps_pending_incidents_separate_by_source(db_session: Session) -> None:
    """Verify pending lookups are scoped by source and conversation id."""

    service = IncidentPersistenceService(db_session)
    telegram_result = service.persist_incident(
        source_context(source="telegram", raw_text="I need medical help"),
        pending_extraction_result(),
    )
    whatsapp_result = service.persist_incident(
        source_context(source="whatsapp", raw_text="I need medical help"),
        pending_extraction_result(),
    )

    assert telegram_result is not None
    assert whatsapp_result is not None
    assert telegram_result.incident_id != whatsapp_result.incident_id
    assert db_session.query(Incident).count() == 2


def test_persist_incident_does_not_create_for_non_incident(db_session: Session) -> None:
    """Verify non-incident extractions are not persisted."""

    service = IncidentPersistenceService(db_session)

    result = service.persist_incident(
        source_context(raw_text="hello"),
        non_incident_extraction_result(),
    )

    assert result is None
    assert db_session.query(Incident).count() == 0


def test_persist_incident_does_not_create_for_none_extraction(db_session: Session) -> None:
    """Verify missing extraction output is not persisted."""

    service = IncidentPersistenceService(db_session)

    result = service.persist_incident(
        source_context(raw_text="hello"),
        None,
    )

    assert result is None
    assert db_session.query(Incident).count() == 0
