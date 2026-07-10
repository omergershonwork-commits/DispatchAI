import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import Base
from app.models.volunteer import (
    DISPATCH_STATUS_DONE,
    DISPATCH_STATUS_SENT,
    VOLUNTEER_STATUS_AVAILABLE,
    VOLUNTEER_STATUS_BUSY,
    VOLUNTEER_STATUS_INACTIVE,
    Volunteer,
    VolunteerDispatch,
)
from app.services.volunteer_management import VolunteerManagementService, VolunteerSourceContext


@pytest.fixture
def db_session() -> Session:
    """Create an isolated in-memory database session for volunteer tests."""

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
    chat_id: int = 987654321,
    user_id: int | None = 111222333,
    username: str | None = "omer_user",
    first_name: str | None = "Omer",
    last_name: str | None = "Volunteer",
    raw_text: str = "/register",
) -> VolunteerSourceContext:
    """Return generic volunteer source metadata for service tests."""

    return VolunteerSourceContext(
        source=source,
        source_chat_id=chat_id,
        source_user_id=user_id,
        source_username=username,
        first_name=first_name,
        last_name=last_name,
        raw_text=raw_text,
    )


def test_process_message_registers_volunteer(db_session: Session) -> None:
    """Verify /register creates an available volunteer."""

    service = VolunteerManagementService(db_session)

    result = service.process_message(source_context(raw_text="/register"))

    assert result.volunteer_id is not None
    assert result.volunteer_status == VOLUNTEER_STATUS_AVAILABLE
    assert result.dispatch_id is None
    assert "registered" in result.reply_text

    volunteer = db_session.get(Volunteer, result.volunteer_id)
    assert volunteer is not None
    assert volunteer.source == "telegram"
    assert volunteer.source_chat_id == 987654321
    assert volunteer.source_user_id == 111222333
    assert volunteer.source_username == "omer_user"
    assert volunteer.display_name == "Omer Volunteer"
    assert volunteer.status == VOLUNTEER_STATUS_AVAILABLE


def test_process_message_reactivates_existing_volunteer(db_session: Session) -> None:
    """Verify /register reactivates an inactive volunteer instead of duplicating it."""

    service = VolunteerManagementService(db_session)
    first_result = service.process_message(source_context(raw_text="/register"))
    stop_result = service.process_message(source_context(raw_text="/stop"))
    second_result = service.process_message(source_context(raw_text="/register"))

    assert first_result.volunteer_id == second_result.volunteer_id
    assert stop_result.volunteer_status == VOLUNTEER_STATUS_INACTIVE
    assert second_result.volunteer_status == VOLUNTEER_STATUS_AVAILABLE
    assert "reactivated" in second_result.reply_text
    assert db_session.query(Volunteer).count() == 1


def test_process_message_marks_latest_dispatch_done(db_session: Session) -> None:
    """Verify done marks the latest active dispatch complete and frees volunteer."""

    service = VolunteerManagementService(db_session)
    register_result = service.process_message(source_context(raw_text="/register"))
    assert register_result.volunteer_id is not None

    dispatch_result = service.create_dispatch_request(
        register_result.volunteer_id,
        "Incident #7 needs medical help near Dizengoff Center.",
        incident_id=7,
    )
    done_result = service.process_message(source_context(raw_text="done"))

    assert dispatch_result.dispatch_id == done_result.dispatch_id
    assert done_result.volunteer_status == VOLUNTEER_STATUS_AVAILABLE
    assert "marked done" in done_result.reply_text

    volunteer = db_session.get(Volunteer, register_result.volunteer_id)
    dispatch = db_session.get(VolunteerDispatch, dispatch_result.dispatch_id)
    assert volunteer is not None
    assert dispatch is not None
    assert volunteer.status == VOLUNTEER_STATUS_AVAILABLE
    assert dispatch.status == DISPATCH_STATUS_DONE
    assert dispatch.completed_at is not None


def test_create_dispatch_request_marks_volunteer_busy(db_session: Session) -> None:
    """Verify dispatch creation records a request and marks volunteer busy."""

    service = VolunteerManagementService(db_session)
    register_result = service.process_message(source_context(raw_text="/register"))
    assert register_result.volunteer_id is not None

    dispatch_result = service.create_dispatch_request(
        register_result.volunteer_id,
        "Please respond to incident #9.",
        incident_id=9,
    )

    volunteer = db_session.get(Volunteer, register_result.volunteer_id)
    dispatch = db_session.get(VolunteerDispatch, dispatch_result.dispatch_id)
    assert volunteer is not None
    assert dispatch is not None
    assert volunteer.status == VOLUNTEER_STATUS_BUSY
    assert dispatch.status == DISPATCH_STATUS_SENT
    assert dispatch.incident_id == 9
    assert dispatch.message_text == "Please respond to incident #9."
    assert dispatch_result.source == "telegram"
    assert dispatch_result.source_chat_id == 987654321


def test_done_without_active_dispatch_returns_safe_message(db_session: Session) -> None:
    """Verify done without active dispatch keeps volunteer available."""

    service = VolunteerManagementService(db_session)
    register_result = service.process_message(source_context(raw_text="/register"))
    done_result = service.process_message(source_context(raw_text="done"))

    assert register_result.volunteer_id == done_result.volunteer_id
    assert done_result.dispatch_id is None
    assert done_result.volunteer_status == VOLUNTEER_STATUS_AVAILABLE
    assert done_result.reply_text == "No active dispatch is assigned to you right now."


def test_done_before_registration_asks_for_registration(db_session: Session) -> None:
    """Verify done from an unknown volunteer does not create a row."""

    service = VolunteerManagementService(db_session)

    result = service.process_message(source_context(raw_text="done"))

    assert result.volunteer_id is None
    assert result.volunteer_status is None
    assert result.dispatch_id is None
    assert result.reply_text == "You are not registered yet. Send /register to join as a volunteer."
    assert db_session.query(Volunteer).count() == 0


def test_volunteers_are_scoped_by_source(db_session: Session) -> None:
    """Verify same chat id from different sources creates separate volunteers."""

    service = VolunteerManagementService(db_session)
    telegram_result = service.process_message(source_context(source="telegram", raw_text="/register"))
    whatsapp_result = service.process_message(source_context(source="whatsapp", raw_text="/register"))

    assert telegram_result.volunteer_id is not None
    assert whatsapp_result.volunteer_id is not None
    assert telegram_result.volunteer_id != whatsapp_result.volunteer_id
    assert db_session.query(Volunteer).count() == 2
