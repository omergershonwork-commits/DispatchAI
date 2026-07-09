from fastapi.testclient import TestClient

from app.api.volunteer_telegram import (
    VOLUNTEER_COMMAND_UNAVAILABLE_ERROR,
    VOLUNTEER_REPLY_UNAVAILABLE_ERROR,
    get_volunteer_management_service,
    get_volunteer_telegram_bot_client,
)
from app.main import app
from app.services.telegram_bot_client import TelegramBotClientError
from app.services.volunteer_management import (
    VolunteerCommandResult,
    VolunteerManagementError,
    VolunteerSourceContext,
)

client = TestClient(app)


class FakeVolunteerManagementService:
    """Test double for volunteer command processing."""

    def __init__(
        self,
        result: VolunteerCommandResult | None = None,
        error: Exception | None = None,
    ) -> None:
        """Create a fake service that returns a result or raises an error."""

        self.result = result
        self.error = error
        self.calls: list[VolunteerSourceContext] = []

    def process_message(self, source_context: VolunteerSourceContext) -> VolunteerCommandResult:
        """Record the source context and return or raise the configured outcome."""

        self.calls.append(source_context)
        if self.error:
            raise self.error
        if self.result is None:
            raise AssertionError("Fake volunteer command result was not configured.")
        return self.result


class FakeTelegramBotClient:
    """Test double for volunteer Telegram replies."""

    def __init__(self, error: Exception | None = None) -> None:
        """Create a fake Telegram client that records sent messages."""

        self.error = error
        self.sent_messages: list[tuple[int, str]] = []

    def send_message(self, chat_id: int, text: str) -> object:
        """Record a Telegram send request or raise the configured error."""

        if self.error:
            raise self.error
        self.sent_messages.append((chat_id, text))
        return object()


def volunteer_text_payload(text: str = "/register") -> dict:
    """Return a valid volunteer Telegram webhook payload with text."""

    return {
        "update_id": 223456,
        "message": {
            "message_id": 52,
            "date": 1_725_000_000,
            "chat": {
                "id": 222333444,
                "type": "private",
                "first_name": "Niv",
            },
            "from": {
                "id": 333444555,
                "is_bot": False,
                "first_name": "Niv",
                "last_name": "Volunteer",
                "username": "niv_volunteer",
            },
            "text": text,
        },
    }


def registered_result() -> VolunteerCommandResult:
    """Return a fake successful registration result."""

    return VolunteerCommandResult(
        volunteer_id=44,
        volunteer_status="available",
        dispatch_id=None,
        reply_text="Volunteer registered. You will receive dispatch messages here when help is needed.",
    )


def done_result() -> VolunteerCommandResult:
    """Return a fake successful done result."""

    return VolunteerCommandResult(
        volunteer_id=44,
        volunteer_status="available",
        dispatch_id=12,
        reply_text="Dispatch #12 marked done. Thank you.",
    )


def override_volunteer_service(fake_service: FakeVolunteerManagementService) -> None:
    """Install a FastAPI dependency override for the volunteer management service."""

    app.dependency_overrides[get_volunteer_management_service] = lambda: fake_service


def override_telegram_bot_client(fake_bot_client: FakeTelegramBotClient) -> None:
    """Install a FastAPI dependency override for the volunteer Telegram bot client."""

    app.dependency_overrides[get_volunteer_telegram_bot_client] = lambda: fake_bot_client


def clear_dependency_overrides() -> None:
    """Clear FastAPI dependency overrides after integration-style tests."""

    app.dependency_overrides.clear()


def test_volunteer_webhook_registers_and_replies() -> None:
    """Verify volunteer webhook maps Telegram text to source context and replies."""

    fake_service = FakeVolunteerManagementService(result=registered_result())
    fake_bot_client = FakeTelegramBotClient()
    override_volunteer_service(fake_service)
    override_telegram_bot_client(fake_bot_client)

    try:
        response = client.post("/webhooks/telegram/volunteers", json=volunteer_text_payload())
    finally:
        clear_dependency_overrides()

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "source": "telegram_volunteer",
        "update_id": 223456,
        "message_id": 52,
        "chat_id": 222333444,
        "has_text": True,
        "volunteer_id": 44,
        "volunteer_status": "available",
        "dispatch_id": None,
        "command_error": None,
        "telegram_reply_sent": True,
        "telegram_reply_error": None,
    }
    assert fake_service.calls == [
        VolunteerSourceContext(
            source="telegram",
            source_chat_id=222333444,
            source_user_id=333444555,
            source_username="niv_volunteer",
            first_name="Niv",
            last_name="Volunteer",
            raw_text="/register",
        )
    ]
    assert fake_bot_client.sent_messages == [(222333444, registered_result().reply_text)]


def test_volunteer_webhook_handles_done_command() -> None:
    """Verify done command result is returned and replied to the volunteer."""

    fake_service = FakeVolunteerManagementService(result=done_result())
    fake_bot_client = FakeTelegramBotClient()
    override_volunteer_service(fake_service)
    override_telegram_bot_client(fake_bot_client)

    try:
        response = client.post("/webhooks/telegram/volunteers", json=volunteer_text_payload("done"))
    finally:
        clear_dependency_overrides()

    assert response.status_code == 202
    assert response.json()["volunteer_id"] == 44
    assert response.json()["volunteer_status"] == "available"
    assert response.json()["dispatch_id"] == 12
    assert response.json()["telegram_reply_sent"] is True
    assert fake_service.calls[0].raw_text == "done"
    assert fake_bot_client.sent_messages == [(222333444, "Dispatch #12 marked done. Thank you.")]


def test_volunteer_webhook_accepts_non_text_without_processing() -> None:
    """Verify non-text volunteer updates are accepted without side effects."""

    fake_service = FakeVolunteerManagementService(result=registered_result())
    fake_bot_client = FakeTelegramBotClient()
    override_volunteer_service(fake_service)
    override_telegram_bot_client(fake_bot_client)
    payload = volunteer_text_payload()
    payload["message"].pop("text")

    try:
        response = client.post("/webhooks/telegram/volunteers", json=payload)
    finally:
        clear_dependency_overrides()

    assert response.status_code == 202
    assert response.json()["has_text"] is False
    assert response.json()["volunteer_id"] is None
    assert response.json()["telegram_reply_sent"] is False
    assert fake_service.calls == []
    assert fake_bot_client.sent_messages == []


def test_volunteer_webhook_accepts_when_command_processing_fails() -> None:
    """Verify command errors return safe metadata and still attempt a reply."""

    fake_service = FakeVolunteerManagementService(error=VolunteerManagementError("db failed"))
    fake_bot_client = FakeTelegramBotClient()
    override_volunteer_service(fake_service)
    override_telegram_bot_client(fake_bot_client)

    try:
        response = client.post("/webhooks/telegram/volunteers", json=volunteer_text_payload())
    finally:
        clear_dependency_overrides()

    assert response.status_code == 202
    assert response.json()["command_error"] == VOLUNTEER_COMMAND_UNAVAILABLE_ERROR
    assert response.json()["telegram_reply_sent"] is True
    assert response.json()["telegram_reply_error"] is None
    assert fake_bot_client.sent_messages == [
        (
            222333444,
            "Volunteer command could not be processed right now. Please try again later.",
        )
    ]


def test_volunteer_webhook_accepts_when_reply_fails() -> None:
    """Verify Telegram reply errors do not make Telegram retry the webhook."""

    fake_service = FakeVolunteerManagementService(result=registered_result())
    fake_bot_client = FakeTelegramBotClient(error=TelegramBotClientError("telegram down"))
    override_volunteer_service(fake_service)
    override_telegram_bot_client(fake_bot_client)

    try:
        response = client.post("/webhooks/telegram/volunteers", json=volunteer_text_payload())
    finally:
        clear_dependency_overrides()

    assert response.status_code == 202
    assert response.json()["volunteer_id"] == 44
    assert response.json()["telegram_reply_sent"] is False
    assert response.json()["telegram_reply_error"] == VOLUNTEER_REPLY_UNAVAILABLE_ERROR


def test_volunteer_webhook_rejects_missing_update_id() -> None:
    """Verify FastAPI validation rejects malformed volunteer webhook updates."""

    payload = volunteer_text_payload()
    del payload["update_id"]

    response = client.post("/webhooks/telegram/volunteers", json=payload)

    assert response.status_code == 422
