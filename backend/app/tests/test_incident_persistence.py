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
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = local()
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
    return SourceIncidentContext(
        source=source,
        source_update_id=update_id,
        source_message_id=message_id,
        source_chat_id=chat_id,
        raw_text=raw_text,
    )


def actionable_extraction_result() -> IncidentExtractionResult:
    return IncidentExtractionResult(
        is_incident=True,
        title="Medical help request",
        summary="Person needs medical help near Dizengoff Center.",
        incident_type="medical",
        location_text="Dizengoff Center",
        urgency="high",
        casualties_text="One person needs assistance",
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
    return IncidentExtractionResult(
        is_incident=True,
        title="Security help request",
        summary="Person needs security assistance.",
        incident_type="security",
        location_text=None,
        urgency="high",
        casualties_text="One person affected",
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
    return IncidentExtractionResult(
        is_incident=False,
        title="Unrelated message",
        summary="Greeting only.",
        incident_type=None,
        location_text=None,
        urgency="unknown",
        casualties_text=None,
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


def test_persist_incident_creates_dashboard_fields(db_session: Session) -> None:
    service = IncidentPersistenceService(db_session)
    result = service.persist_incident(source_context(), actionable_extraction_result())

    assert result is not None
    assert result.status == INCIDENT_STATUS_READY_FOR_DISPATCH
    incident = db_session.get(Incident, result.incident_id)
    assert incident is not None
    assert incident.title == "Medical help request"
    assert incident.casualties_text == "One person needs assistance"
    assert incident.confidence == 0.91
    assert incident.metadata_json["assigned_forces"] == []


def test_persist_incident_creates_pending_incident(db_session: Session) -> None:
    service = IncidentPersistenceService(db_session)
    result = service.persist_incident(
        source_context(raw_text="Someone needs security assistance"),
        pending_extraction_result(),
    )

    assert result is not None
    assert result.status == INCIDENT_STATUS_PENDING_DETAILS
    incident = db_session.get(Incident, result.incident_id)
    assert incident is not None
    assert incident.metadata_json["follow_up_question"] == "Where exactly is help needed?"


def test_build_extraction_text_includes_new_pending_context(db_session: Session) -> None:
    service = IncidentPersistenceService(db_session)
    service.persist_incident(
        source_context(raw_text="Someone needs security assistance"),
        pending_extraction_result(),
    )

    extraction_text = service.build_extraction_text(
        source_context(update_id=123457, message_id=43, raw_text="White House")
    )

    assert "Existing title: Security help request" in extraction_text
    assert "Existing affected-person details: One person affected" in extraction_text
    assert "Existing incident type: security" in extraction_text
    assert "Latest sender message: White House" in extraction_text


def test_pending_update_preserves_assigned_forces_metadata(db_session: Session) -> None:
    service = IncidentPersistenceService(db_session)
    first_result = service.persist_incident(
        source_context(raw_text="Someone needs security assistance"),
        pending_extraction_result(),
    )
    assert first_result is not None

    incident = db_session.get(Incident, first_result.incident_id)
    assert incident is not None
    incident.metadata_json = {
        **incident.metadata_json,
        "assigned_forces": [
            {"volunteer_id": 12, "name": "Mordehai", "status": "pending_response"}
        ],
    }
    db_session.commit()

    follow_up = actionable_extraction_result().copy(
        update={
            "title": "Security assistance request",
            "summary": "Person needs security assistance at the White House.",
            "incident_type": "security",
            "location_text": "White House",
            "casualties_text": "One person affected",
            "needs": ["security assistance"],
        }
    )
    second_result = service.persist_incident(
        source_context(update_id=123457, message_id=43, raw_text="White House"),
        follow_up,
    )

    assert second_result is not None
    assert second_result.incident_id == first_result.incident_id
    assert second_result.status == INCIDENT_STATUS_READY_FOR_DISPATCH
    db_session.refresh(incident)
    assert incident.location_text == "White House"
    assert incident.title == "Security assistance request"
    assert incident.metadata_json["assigned_forces"][0]["volunteer_id"] == 12


def test_pending_incidents_are_scoped_by_source(db_session: Session) -> None:
    service = IncidentPersistenceService(db_session)
    telegram_result = service.persist_incident(
        source_context(source="telegram", raw_text="Security assistance needed"),
        pending_extraction_result(),
    )
    whatsapp_result = service.persist_incident(
        source_context(source="whatsapp", raw_text="Security assistance needed"),
        pending_extraction_result(),
    )

    assert telegram_result is not None
    assert whatsapp_result is not None
    assert telegram_result.incident_id != whatsapp_result.incident_id


def test_non_incident_and_none_are_not_persisted(db_session: Session) -> None:
    service = IncidentPersistenceService(db_session)
    assert service.persist_incident(source_context(raw_text="hello"), non_incident_extraction_result()) is None
    assert service.persist_incident(source_context(raw_text="hello"), None) is None
    assert db_session.query(Incident).count() == 0
