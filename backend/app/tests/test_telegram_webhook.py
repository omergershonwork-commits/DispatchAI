from fastapi.testclient import TestClient

from app.api.telegram import (
    EXTRACTION_UNAVAILABLE_ERROR,
    TELEGRAM_REPLY_UNAVAILABLE_ERROR,
    get_incident_extraction_service,
    get_telegram_bot_client,
)
from app.main import app
from app.schemas.incident import IncidentExtractionResult
from app.services.incident_extraction import IncidentExtractionError
from app.services.telegram_bot_client import TelegramBotClientError

client = TestClient(app)


class FakeIncidentExtractionService:
    """Test double for Telegram-to-extraction integration tests."""

    def __init__(
        self,
        result: IncidentExtractionResult | None = None,
        error: Exception | None = None,
    ) -> None:
        """Create a fake service that returns a result or raises an error."""

        self.result = result
        """Incident extraction result returned by the fake service."""

        self.error = error
        """Exception raised by the fake service, when configured."""

        self.last_message_text: str | None = None
        """Most recent Telegram text passed into extraction."""

    def extract_from_text(self, message_text: str) -> IncidentExtractionResult:
        """Record text and return or raise the configured fake outcome."""

        self.last_message_text = message_text
        if self.error:
            raise self.error
        if self.result is None:
            raise AssertionError("Fake extraction service result was not configured.")
        return self.result


class FakeTelegramBotClient:
    """Test double for Telegram Bot API reply tests."""

    def __init__(self, error: Exception | None = None) -> None:
        """Create a fake client that records sent messages or raises an error."""

        self.error = error
        """Exception raised by the fake client, when configured."""

        self.sent_messages: list[tuple[int, str]] = []
        """Telegram messages sent through the fake client."""

    def send_message(self, chat_id: int, text: str) -> object:
        """Record a Telegram message send request."""

        if self.error:
            raise self.error
        self.sent_messages.append((chat_id, text))
        return object()


def telegram_text_payload() -> dict:
    """Return a valid Telegram webhook payload with a text message."""

    return {
        "update_id": 123456,
        "message": {
            "message_id": 42,
            "date": 1_725_000_000,
            "chat": {
                "id": 987654321,
                "type": "private",
                "first_name": "Omer",
            },
            "from": {
                "id": 111222333,
                "is_bot": False,
                "first_name": "Omer",
                "username": "omer_user",
            },
            "text": "I need medical help near Dizengoff Center",
        },
    }


def actionable_extraction_result() -> IncidentExtractionResult:
    """Return an actionable incident extraction result for webhook tests."""

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


def follow_up_extraction_result() -> IncidentExtractionResult:
    """Return an incident extraction result that needs a follow-up question."""

    return IncidentExtractionResult(
        is_incident=True,
        summary="Person needs help.",
        incident_type="medical",
        location_text=None,
        urgency="unknown",
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


def override_extraction_service(fake_service: FakeIncidentExtractionService) -> None:
    """Install a FastAPI dependency override for the extraction service."""

    app.dependency_overrides[get_incident_extraction_service] = lambda: fake_service


def override_telegram_bot_client(fake_bot_client: FakeTelegramBotClient) -> None:
    """Install a FastAPI dependency override for the Telegram bot client."""

    app.dependency_overrides[get_telegram_bot_client] = lambda: fake_bot_client


def clear_dependency_overrides() -> None:
    """Clear FastAPI dependency overrides after an integration-style test."""

    app.dependency_overrides.clear()


def test_telegram_webhook_accepts_text_message_runs_extraction_and_replies() -> None:
    """Verify text webhooks run extraction and send a Telegram reply."""

    fake_service = FakeIncidentExtractionService(result=actionable_extraction_result())
    fake_bot_client = FakeTelegramBotClient()
    override_extraction_service(fake_service)
    override_telegram_bot_client(fake_bot_client)

    try:
        response = client.post("/webhooks/telegram", json=telegram_text_payload())
    finally:
        clear_dependency_overrides()

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "source": "telegram",
        "update_id": 123456,
        "message_id": 42,
        "chat_id": 987654321,
        "has_text": True,
        "extraction": {
            "is_incident": True,
            "summary": "Person needs medical help near Dizengoff Center.",
            "incident_type": "medical",
            "location_text": "Dizengoff Center",
            "urgency": "high",
            "people_count": 1,
            "contact_name": "Omer",
            "phone_number": "0501234567",
            "needs": ["medical help"],
            "confidence": 0.91,
            "missing_fields": [],
            "follow_up_question": None,
            "should_create_incident": True,
            "should_ask_follow_up": False,
            "rejection_reason": None,
        },
        "extraction_error": None,
        "telegram_reply_sent": True,
        "telegram_reply_error": None,
    }
    assert fake_service.last_message_text == "I need medical help near Dizengoff Center"
    assert fake_bot_client.sent_messages == [
        (
            987654321,
            "Incident report received.\n"
            "Summary: Person needs medical help near Dizengoff Center.\n"
            "Location: Dizengoff Center\n"
            "Urgency: high\n"
            "Needs: medical help\n"
            "I will keep tracking this report while dispatch support is being prepared.",
        )
    ]


def test_telegram_webhook_sends_follow_up_question_when_extraction_needs_details() -> None:
    """Verify the webhook replies with the extraction follow-up question when needed."""

    fake_service = FakeIncidentExtractionService(result=follow_up_extraction_result())
    fake_bot_client = FakeTelegramBotClient()
    override_extraction_service(fake_service)
    override_telegram_bot_client(fake_bot_client)

    try:
        response = client.post("/webhooks/telegram", json=telegram_text_payload())
    finally:
        clear_dependency_overrides()

    assert response.status_code == 202
    assert response.json()["telegram_reply_sent"] is True
    assert response.json()["telegram_reply_error"] is None
    assert fake_bot_client.sent_messages == [(987654321, "Where exactly is help needed?")]


def test_telegram_webhook_accepts_update_without_message() -> None:
    """Verify non-message updates are accepted without incident extraction."""

    response = client.post("/webhooks/telegram", json={"update_id": 123457})

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "source": "telegram",
        "update_id": 123457,
        "message_id": None,
        "chat_id": None,
        "has_text": False,
        "extraction": None,
        "extraction_error": None,
        "telegram_reply_sent": False,
        "telegram_reply_error": None,
    }


def test_telegram_webhook_accepts_non_text_message_without_extraction_or_reply() -> None:
    """Verify non-text Telegram messages do not call extraction or reply sending."""

    fake_service = FakeIncidentExtractionService(result=actionable_extraction_result())
    fake_bot_client = FakeTelegramBotClient()
    override_extraction_service(fake_service)
    override_telegram_bot_client(fake_bot_client)
    payload = telegram_text_payload()
    payload["message"].pop("text")

    try:
        response = client.post("/webhooks/telegram", json=payload)
    finally:
        clear_dependency_overrides()

    assert response.status_code == 202
    assert response.json()["has_text"] is False
    assert response.json()["extraction"] is None
    assert response.json()["extraction_error"] is None
    assert response.json()["telegram_reply_sent"] is False
    assert response.json()["telegram_reply_error"] is None
    assert fake_service.last_message_text is None
    assert fake_bot_client.sent_messages == []


def test_telegram_webhook_accepts_when_extraction_fails_and_sends_safe_reply() -> None:
    """Verify extraction failure does not make Telegram retry and still sends a reply."""

    fake_service = FakeIncidentExtractionService(error=IncidentExtractionError("bad model output"))
    fake_bot_client = FakeTelegramBotClient()
    override_extraction_service(fake_service)
    override_telegram_bot_client(fake_bot_client)

    try:
        response = client.post("/webhooks/telegram", json=telegram_text_payload())
    finally:
        clear_dependency_overrides()

    assert response.status_code == 202
    assert response.json()["extraction"] is None
    assert response.json()["extraction_error"] == EXTRACTION_UNAVAILABLE_ERROR
    assert response.json()["telegram_reply_sent"] is True
    assert response.json()["telegram_reply_error"] is None
    assert fake_service.last_message_text == "I need medical help near Dizengoff Center"
    assert fake_bot_client.sent_messages == [
        (
            987654321,
            "I received your message, but I could not extract the incident details yet. "
            "Please send the location and what help is needed.",
        )
    ]


def test_telegram_webhook_accepts_when_reply_sending_fails() -> None:
    """Verify Telegram reply failure does not make Telegram retry the webhook."""

    fake_service = FakeIncidentExtractionService(result=actionable_extraction_result())
    fake_bot_client = FakeTelegramBotClient(error=TelegramBotClientError("telegram unavailable"))
    override_extraction_service(fake_service)
    override_telegram_bot_client(fake_bot_client)

    try:
        response = client.post("/webhooks/telegram", json=telegram_text_payload())
    finally:
        clear_dependency_overrides()

    assert response.status_code == 202
    assert response.json()["extraction"] is not None
    assert response.json()["extraction_error"] is None
    assert response.json()["telegram_reply_sent"] is False
    assert response.json()["telegram_reply_error"] == TELEGRAM_REPLY_UNAVAILABLE_ERROR


def test_telegram_webhook_rejects_missing_update_id() -> None:
    """Verify FastAPI validation rejects payloads without Telegram update_id."""

    payload = telegram_text_payload()
    del payload["update_id"]

    response = client.post("/webhooks/telegram", json=payload)

    assert response.status_code == 422


def test_telegram_webhook_rejects_invalid_message_shape() -> None:
    """Verify FastAPI validation rejects malformed Telegram message payloads."""

    payload = telegram_text_payload()
    payload["message"]["chat"] = None

    response = client.post("/webhooks/telegram", json=payload)

    assert response.status_code == 422
