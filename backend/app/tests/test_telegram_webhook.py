from fastapi.testclient import TestClient

from app.api.telegram import (
    EXTRACTION_UNAVAILABLE_ERROR,
    INCIDENT_PERSISTENCE_UNAVAILABLE_ERROR,
    TELEGRAM_REPLY_UNAVAILABLE_ERROR,
    get_incident_extraction_service,
    get_incident_persistence_service,
    get_telegram_bot_client,
)
from app.main import app
from app.schemas.incident import IncidentExtractionResult
from app.services.incident_extraction import IncidentExtractionError
from app.services.incident_persistence import (
    IncidentPersistenceError,
    IncidentPersistenceResult,
    SourceIncidentContext,
)
from app.services.telegram_bot_client import TelegramBotClientError

client = TestClient(app)


class FakeIncidentExtractionService:
    def __init__(
        self,
        result: IncidentExtractionResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.last_message_text: str | None = None

    def extract_from_text(self, message_text: str) -> IncidentExtractionResult:
        self.last_message_text = message_text
        if self.error:
            raise self.error
        if self.result is None:
            raise AssertionError("Fake extraction result was not configured.")
        return self.result


class FakeIncidentPersistenceService:
    def __init__(
        self,
        result: IncidentPersistenceResult | None = None,
        error: Exception | None = None,
        extraction_text: str | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.extraction_text = extraction_text
        self.calls: list[tuple[SourceIncidentContext, IncidentExtractionResult | None]] = []

    def build_extraction_text(self, source_context: SourceIncidentContext) -> str:
        return self.extraction_text or source_context.raw_text

    def persist_incident(
        self,
        source_context: SourceIncidentContext,
        extraction: IncidentExtractionResult | None,
    ) -> IncidentPersistenceResult | None:
        self.calls.append((source_context, extraction))
        if self.error:
            raise self.error
        return self.result


class FakeTelegramBotClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.sent_messages: list[tuple[int, str]] = []

    def send_message(self, chat_id: int, text: str) -> object:
        if self.error:
            raise self.error
        self.sent_messages.append((chat_id, text))
        return object()


def telegram_text_payload(text: str = "I need medical help near Dizengoff Center") -> dict:
    return {
        "update_id": 123456,
        "message": {
            "message_id": 42,
            "date": 1_725_000_000,
            "chat": {"id": 987654321, "type": "private", "first_name": "Omer"},
            "from": {
                "id": 111222333,
                "is_bot": False,
                "first_name": "Omer",
                "username": "omer_user",
            },
            "text": text,
        },
    }


def actionable_extraction_result() -> IncidentExtractionResult:
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
    return IncidentExtractionResult(
        is_incident=True,
        summary="Person needs help.",
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


def persisted_result(
    incident_id: int = 123,
    status: str = "ready_for_dispatch",
) -> IncidentPersistenceResult:
    return IncidentPersistenceResult(
        incident_id=incident_id,
        status=status,
        created=True,
        updated=False,
    )


def install_overrides(
    extraction_service: FakeIncidentExtractionService,
    persistence_service: FakeIncidentPersistenceService,
    bot_client: FakeTelegramBotClient,
) -> None:
    app.dependency_overrides[get_incident_extraction_service] = lambda: extraction_service
    app.dependency_overrides[get_incident_persistence_service] = lambda: persistence_service
    app.dependency_overrides[get_telegram_bot_client] = lambda: bot_client


def test_webhook_uses_pending_context_persists_and_sends_user_facing_reply() -> None:
    extraction_service = FakeIncidentExtractionService(result=actionable_extraction_result())
    persistence_service = FakeIncidentPersistenceService(
        result=persisted_result(),
        extraction_text="Previous report plus latest location",
    )
    bot_client = FakeTelegramBotClient()
    install_overrides(extraction_service, persistence_service, bot_client)

    try:
        response = client.post("/webhooks/telegram", json=telegram_text_payload("White House"))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert extraction_service.last_message_text == "Previous report plus latest location"
    assert response.json()["incident_id"] == 123
    assert response.json()["incident_status"] == "ready_for_dispatch"
    assert len(persistence_service.calls) == 1
    assert bot_client.sent_messages == [
        (
            987654321,
            "Your emergency report has been received and saved. "
            "Available volunteers are now being matched. "
            "A responder has not yet been confirmed. "
            "If there is immediate danger, contact local emergency services now.",
        )
    ]


def test_webhook_sends_contextual_follow_up() -> None:
    extraction_service = FakeIncidentExtractionService(result=follow_up_extraction_result())
    persistence_service = FakeIncidentPersistenceService(
        result=persisted_result(incident_id=124, status="pending_details")
    )
    bot_client = FakeTelegramBotClient()
    install_overrides(extraction_service, persistence_service, bot_client)

    try:
        response = client.post("/webhooks/telegram", json=telegram_text_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["incident_status"] == "pending_details"
    assert bot_client.sent_messages == [
        (
            987654321,
            "Your report has been received. I need one more detail before it can be matched.\n"
            "Where exactly is help needed?\n"
            "You can type the address or share your Telegram location.\n"
            "You can send /cancel to discard this unfinished report or /new to start over.\n"
            "If there is immediate danger, contact local emergency services now.",
        )
    ]


def test_webhook_accepts_extraction_failure_and_sends_safe_reply() -> None:
    extraction_service = FakeIncidentExtractionService(
        error=IncidentExtractionError("invalid output")
    )
    persistence_service = FakeIncidentPersistenceService()
    bot_client = FakeTelegramBotClient()
    install_overrides(extraction_service, persistence_service, bot_client)

    try:
        response = client.post("/webhooks/telegram", json=telegram_text_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["extraction_error"] == EXTRACTION_UNAVAILABLE_ERROR
    assert persistence_service.calls == []
    assert bot_client.sent_messages[0][1].startswith(
        "I received your message, but I still need clearer details."
    )


def test_webhook_accepts_persistence_failure_and_sends_resend_reply() -> None:
    extraction_service = FakeIncidentExtractionService(result=actionable_extraction_result())
    persistence_service = FakeIncidentPersistenceService(
        error=IncidentPersistenceError("db unavailable")
    )
    bot_client = FakeTelegramBotClient()
    install_overrides(extraction_service, persistence_service, bot_client)

    try:
        response = client.post("/webhooks/telegram", json=telegram_text_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["persistence_error"] == INCIDENT_PERSISTENCE_UNAVAILABLE_ERROR
    assert bot_client.sent_messages[0][1].startswith(
        "I understood your report, but I could not save it."
    )


def test_webhook_accepts_reply_failure() -> None:
    extraction_service = FakeIncidentExtractionService(result=actionable_extraction_result())
    persistence_service = FakeIncidentPersistenceService(result=persisted_result())
    bot_client = FakeTelegramBotClient(error=TelegramBotClientError("telegram unavailable"))
    install_overrides(extraction_service, persistence_service, bot_client)

    try:
        response = client.post("/webhooks/telegram", json=telegram_text_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["telegram_reply_sent"] is False
    assert response.json()["telegram_reply_error"] == TELEGRAM_REPLY_UNAVAILABLE_ERROR


def test_webhook_accepts_non_text_update_without_processing() -> None:
    payload = telegram_text_payload()
    payload["message"].pop("text")

    response = client.post("/webhooks/telegram", json=payload)

    assert response.status_code == 202
    assert response.json()["has_text"] is False
    assert response.json()["extraction"] is None


def test_webhook_rejects_missing_update_id() -> None:
    payload = telegram_text_payload()
    del payload["update_id"]

    response = client.post("/webhooks/telegram", json=payload)

    assert response.status_code == 422
