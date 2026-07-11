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
        summary="Person needs security assistance.",
        incident_type="security",
        location_text=None,
        urgency="high",
        people_count=1,
        contact_name=None,
        phone_number=None,
        needs=["security assistance"],
        confidence=0.8,
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
    service = IncidentPersistenceService(db_session)

    result = service.persist_incident(source_context(), actionable_extraction_result())

    assert result is not None
    assert result.created is True
    assert result.updated is False
    assert result.status == INCIDENT_STATUS_READY_FOR_DISPATCH

    incident = db_session.get(Incident, result.incident_id)
    assert incident is not None
    assert incident.source == "telegram"
    assert incident.location_text == "Dizengoff Center"
    assert incident.needs == ["medical help"]


def test_persist_incident_creates_pending_incident(db_session: Session) -> None:
    service = IncidentPersistenceService(db_session)

    result = service.persist_incident(
        source_context(raw_text="Someone is robbing me"),
        pending_extraction_result(),
    )

    assert result is not None
    assert result.status == INCIDENT_STATUS_PENDING_DETAILS
    incident = db_session.get(Incident, result.incident_id)
    assert incident is not None
    assert incident.incident_type == "security"
    assert incident.metadata_json["follow_up_question"] == "Where exactly is help needed?"


def test_build_extraction_text_includes_pending_context_and_latest_message(
    db_session: Session,
) -> None:
    """Verify a short follow-up is combined with the pending incident facts."""

    service = IncidentPersistenceService(db_session)
    service.persist_incident(
        source_context(raw_text="Someone is robbing me"),
        pending_extraction_result(),
    )

    extraction_text = service.build_extraction_text(
        source_context(
            update_id=123457,
            message_id=43,
            raw_text="White House",
        )
    )

    assert "Existing incident type: security" in extraction_text
    assert "Existing needs: security assistance" in extraction_text
    assert "Previous conversation: Someone is robbing me" in extraction_text
    assert "Latest sender message: White House" in extraction_text
    assert "Merge the latest message" in extraction_text


def test_persist_incident_updates_existing_pending_incident(db_session: Session) -> None:
    service = IncidentPersistenceService(db_session)
    first_result = service.persist_incident(
        source_context(raw_text="Someone is robbing me"),
        pending_extraction_result(),
    )

    follow_up_result = actionable_extraction_result().copy(
        update={
            "summary": "Person needs security assistance at the White House.",
            "incident_type": "security",
            "location_text": "White House",
            "needs": ["security assistance"],
        }
    )
    second_result = service.persist_incident(
        source_context(
            update_id=123457,
            message_id=43,
            raw_text="White House",
        ),
        follow_up_result,
    )

    assert first_result is not None
    assert second_result is not None
    assert second_result.incident_id == first_result.incident_id
    assert second_result.created is False
    assert second_result.updated is True
    assert second_result.status == INCIDENT_STATUS_READY_FOR_DISPATCH

    incident = db_session.get(Incident, second_result.incident_id)
    assert incident is not None
    assert incident.location_text == "White House"
    assert incident.source_message_id == 43
    assert "--- follow-up ---" in incident.raw_text


def test_pending_incidents_are_scoped_by_source(db_session: Session) -> None:
    service = IncidentPersistenceService(db_session)

    telegram_result = service.persist_incident(
        source_context(source="telegram", raw_text="Someone is robbing me"),
        pending_extraction_result(),
    )
    whatsapp_result = service.persist_incident(
        source_context(source="whatsapp", raw_text="Someone is robbing me"),
        pending_extraction_result(),
    )

    assert telegram_result is not None
    assert whatsapp_result is not None
    assert telegram_result.incident_id != whatsapp_result.incident_id


def test_non_incident_and_none_extraction_are_not_persisted(db_session: Session) -> None:
    service = IncidentPersistenceService(db_session)

    assert service.persist_incident(
        source_context(raw_text="hello"),
        non_incident_extraction_result(),
    ) is None
    assert service.persist_incident(source_context(raw_text="hello"), None) is None
    assert db_session.query(Incident).count() == 0
