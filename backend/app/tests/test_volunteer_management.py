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
    raw_text: str,
    source: str = "telegram",
    chat_id: int = 987654321,
    user_id: int | None = 111222333,
    username: str | None = "omer_user",
    first_name: str | None = "Omer",
    last_name: str | None = "Volunteer",
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


def complete_registration(
    service: VolunteerManagementService,
    source: str = "telegram",
    chat_id: int = 987654321,
    available: str = "yes",
):
    """Complete the persisted registration wizard and return the final result."""

    result = service.process_message(source_context("/register", source=source, chat_id=chat_id))
    for answer in (
        "Omer Gershon",
        "Tel Aviv",
        "medical, rescue, transport",
        "car",
        "20",
        "0501234567",
        available,
    ):
        result = service.process_message(source_context(answer, source=source, chat_id=chat_id))
    return result


def test_register_starts_persisted_wizard(db_session: Session) -> None:
    """Verify /register creates an inactive draft and asks for the first profile field."""

    service = VolunteerManagementService(db_session)

    result = service.process_message(source_context("/register"))

    assert result.volunteer_id is not None
    assert result.volunteer_status == VOLUNTEER_STATUS_INACTIVE
    assert "Registration 1/7" in result.reply_text

    volunteer = db_session.get(Volunteer, result.volunteer_id)
    assert volunteer is not None
    assert volunteer.status == VOLUNTEER_STATUS_INACTIVE
    assert volunteer.metadata_json["registration_step"] == "full_name"
    assert volunteer.metadata_json["registration_complete"] is False


def test_registration_wizard_collects_matching_profile(db_session: Session) -> None:
    """Verify the wizard stores all fields required by volunteer matching."""

    service = VolunteerManagementService(db_session)

    result = complete_registration(service)

    assert result.volunteer_id is not None
    assert result.volunteer_status == VOLUNTEER_STATUS_AVAILABLE
    assert "Registration complete" in result.reply_text

    volunteer = db_session.get(Volunteer, result.volunteer_id)
    assert volunteer is not None
    assert volunteer.display_name == "Omer Gershon"
    assert volunteer.status == VOLUNTEER_STATUS_AVAILABLE
    assert volunteer.metadata_json == {
        "registration_step": None,
        "registration_complete": True,
        "service_areas": ["Tel Aviv"],
        "location_text": "Tel Aviv",
        "skills": ["medical", "rescue", "transport"],
        "vehicle": "car",
        "max_distance_km": 20.0,
        "phone_number": "0501234567",
        "available_now": True,
    }


def test_registration_repeats_invalid_distance_question(db_session: Session) -> None:
    """Verify invalid distance does not advance the registration wizard."""

    service = VolunteerManagementService(db_session)
    service.process_message(source_context("/register"))
    for answer in ("Omer Gershon", "Tel Aviv", "medical", "car"):
        service.process_message(source_context(answer))

    result = service.process_message(source_context("very far"))

    assert "Please send a number of kilometers" in result.reply_text
    assert "Registration 5/7" in result.reply_text
    volunteer = db_session.get(Volunteer, result.volunteer_id)
    assert volunteer is not None
    assert volunteer.metadata_json["registration_step"] == "max_distance_km"


def test_status_reports_incomplete_registration_step(db_session: Session) -> None:
    """Verify /status resumes the current registration question."""

    service = VolunteerManagementService(db_session)
    register_result = service.process_message(source_context("/register"))
    service.process_message(source_context("Omer Gershon"))

    result = service.process_message(source_context("/status"))

    assert result.volunteer_id == register_result.volunteer_id
    assert "Registration is incomplete" in result.reply_text
    assert "Registration 2/7" in result.reply_text


def test_create_dispatch_rejects_incomplete_registration(db_session: Session) -> None:
    """Verify a registration draft cannot receive dispatch requests."""

    service = VolunteerManagementService(db_session)
    result = service.process_message(source_context("/register"))
    assert result.volunteer_id is not None

    with pytest.raises(ValueError, match="registration is incomplete"):
        service.create_dispatch_request(result.volunteer_id, "Please respond.")


def test_create_dispatch_and_done_after_registration(db_session: Session) -> None:
    """Verify a completed volunteer can receive and finish a dispatch."""

    service = VolunteerManagementService(db_session)
    registration = complete_registration(service)
    assert registration.volunteer_id is not None

    dispatch_result = service.create_dispatch_request(
        registration.volunteer_id,
        "Please respond to incident #9.",
        incident_id=9,
    )
    done_result = service.process_message(source_context("done"))

    assert dispatch_result.dispatch_id == done_result.dispatch_id
    assert done_result.volunteer_status == VOLUNTEER_STATUS_AVAILABLE

    volunteer = db_session.get(Volunteer, registration.volunteer_id)
    dispatch = db_session.get(VolunteerDispatch, dispatch_result.dispatch_id)
    assert volunteer is not None
    assert dispatch is not None
    assert volunteer.status == VOLUNTEER_STATUS_AVAILABLE
    assert dispatch.status == DISPATCH_STATUS_DONE
    assert dispatch.completed_at is not None


def test_dispatch_creation_marks_volunteer_busy(db_session: Session) -> None:
    """Verify dispatch creation stores the assignment and marks the volunteer busy."""

    service = VolunteerManagementService(db_session)
    registration = complete_registration(service)
    assert registration.volunteer_id is not None

    dispatch_result = service.create_dispatch_request(
        registration.volunteer_id,
        "Please respond to incident #7.",
        incident_id=7,
    )

    volunteer = db_session.get(Volunteer, registration.volunteer_id)
    dispatch = db_session.get(VolunteerDispatch, dispatch_result.dispatch_id)
    assert volunteer is not None
    assert dispatch is not None
    assert volunteer.status == VOLUNTEER_STATUS_BUSY
    assert dispatch.status == DISPATCH_STATUS_SENT
    assert dispatch.incident_id == 7


def test_registration_can_complete_as_inactive(db_session: Session) -> None:
    """Verify a complete profile remains inactive when availability answer is no."""

    service = VolunteerManagementService(db_session)

    result = complete_registration(service, available="no")

    assert result.volunteer_status == VOLUNTEER_STATUS_INACTIVE
    volunteer = db_session.get(Volunteer, result.volunteer_id)
    assert volunteer is not None
    assert volunteer.metadata_json["registration_complete"] is True
    assert volunteer.metadata_json["available_now"] is False


def test_volunteers_are_scoped_by_source(db_session: Session) -> None:
    """Verify identical chat ids from different sources create separate profiles."""

    service = VolunteerManagementService(db_session)

    telegram_result = complete_registration(service, source="telegram")
    whatsapp_result = complete_registration(service, source="whatsapp")

    assert telegram_result.volunteer_id is not None
    assert whatsapp_result.volunteer_id is not None
    assert telegram_result.volunteer_id != whatsapp_result.volunteer_id
    assert db_session.query(Volunteer).count() == 2
