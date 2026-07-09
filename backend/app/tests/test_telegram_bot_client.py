import json

import httpx
import pytest

from app.services.telegram_bot_client import TelegramBotClient, TelegramBotClientError


def telegram_send_message_response() -> dict:
    """Return a minimal successful Telegram sendMessage response payload."""

    return {
        "ok": True,
        "result": {
            "message_id": 77,
        },
    }


def test_telegram_bot_client_sends_expected_request_shape() -> None:
    """Verify Telegram bot client sends the expected sendMessage request."""

    captured_request: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        """Capture the outgoing request and return a successful Telegram response."""

        captured_request["url"] = str(request.url)
        captured_request["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=telegram_send_message_response(), request=request)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = TelegramBotClient(
        bot_token="test-token",
        api_base_url="https://telegram.test",
        timeout_seconds=5,
        http_client=http_client,
    )

    result = client.send_message(987654321, "Incident report received.")

    assert captured_request["url"] == "https://telegram.test/bottest-token/sendMessage"
    assert captured_request["payload"] == {
        "chat_id": 987654321,
        "text": "Incident report received.",
    }
    assert result.message_id == 77
    assert result.raw_response["ok"] is True


def test_telegram_bot_client_rejects_missing_token() -> None:
    """Verify Telegram bot client fails clearly when the token is missing."""

    client = TelegramBotClient(bot_token="")

    with pytest.raises(TelegramBotClientError, match="token"):
        client.send_message(987654321, "Incident report received.")


def test_telegram_bot_client_rejects_empty_text() -> None:
    """Verify Telegram bot client fails fast when reply text is empty."""

    client = TelegramBotClient(bot_token="test-token")

    with pytest.raises(ValueError, match="must not be empty"):
        client.send_message(987654321, "   ")


def test_telegram_bot_client_raises_clear_error_on_timeout() -> None:
    """Verify Telegram bot client wraps timeouts in a domain-specific error."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Simulate a read timeout from Telegram."""

        raise httpx.ReadTimeout("request timed out", request=request)

    client = TelegramBotClient(bot_token="test-token", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(TelegramBotClientError, match="timed out"):
        client.send_message(987654321, "Incident report received.")


def test_telegram_bot_client_raises_clear_error_on_non_200_response() -> None:
    """Verify Telegram bot client reports non-success HTTP responses clearly."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Return a Telegram API error response."""

        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"}, request=request)

    client = TelegramBotClient(bot_token="test-token", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(TelegramBotClientError, match="HTTP 401"):
        client.send_message(987654321, "Incident report received.")


def test_telegram_bot_client_raises_clear_error_when_response_not_ok() -> None:
    """Verify Telegram bot client rejects JSON responses where ok is false."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Return a 200 response with ok=false."""

        return httpx.Response(200, json={"ok": False, "description": "chat not found"}, request=request)

    client = TelegramBotClient(bot_token="test-token", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(TelegramBotClientError, match="not ok"):
        client.send_message(987654321, "Incident report received.")
