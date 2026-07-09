from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings

SEND_MESSAGE_METHOD = "sendMessage"
"""Telegram Bot API method used to send chat replies."""


class TelegramBotClientError(RuntimeError):
    """Raised when the backend cannot send a Telegram bot message."""


@dataclass(frozen=True)
class TelegramSendMessageResult:
    """Normalized result returned after sending a Telegram message."""

    message_id: int | None
    """Telegram message identifier returned by the Bot API, when available."""

    raw_response: dict[str, Any]
    """Raw JSON response returned by the Telegram Bot API."""


class TelegramBotClient:
    """Small HTTP client for Telegram Bot API send-message calls."""

    def __init__(
        self,
        bot_token: str = settings.telegram_bot_token,
        api_base_url: str = settings.telegram_api_base_url,
        timeout_seconds: float = settings.telegram_timeout_seconds,
        http_client: httpx.Client | None = None,
    ) -> None:
        """Create a Telegram Bot API client with injectable HTTP transport for tests."""

        self.bot_token = bot_token.strip()
        """Telegram bot token used in Bot API URLs."""

        self.api_base_url = api_base_url.rstrip("/")
        """Telegram Bot API base URL without a trailing slash."""

        self.timeout_seconds = timeout_seconds
        """Request timeout in seconds."""

        self._http_client = http_client
        """Optional externally owned HTTP client used for tests or custom transports."""

    def send_message(self, chat_id: int, text: str) -> TelegramSendMessageResult:
        """Send a plain-text Telegram message to a chat."""

        if not self.bot_token:
            raise TelegramBotClientError("Telegram bot token is not configured.")
        if not text.strip():
            raise ValueError("Telegram reply text must not be empty.")

        payload = {
            "chat_id": chat_id,
            "text": text,
        }
        response_json = self._post_telegram_method(SEND_MESSAGE_METHOD, payload)
        result = response_json.get("result")

        message_id: int | None = None
        if isinstance(result, dict) and isinstance(result.get("message_id"), int):
            message_id = result["message_id"]

        return TelegramSendMessageResult(message_id=message_id, raw_response=response_json)

    def _post_telegram_method(self, method_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Post a JSON payload to a Telegram Bot API method endpoint."""

        url = f"{self.api_base_url}/bot{self.bot_token}/{method_name}"
        timeout = httpx.Timeout(self.timeout_seconds)

        try:
            if self._http_client is not None:
                response = self._http_client.post(url, json=payload, timeout=timeout)
            else:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(url, json=payload)

            response.raise_for_status()
            response_json = response.json()
        except httpx.TimeoutException as exc:
            raise TelegramBotClientError("Telegram sendMessage request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise TelegramBotClientError(f"Telegram sendMessage failed with HTTP {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            raise TelegramBotClientError("Telegram sendMessage failed before a response was parsed.") from exc
        except ValueError as exc:
            raise TelegramBotClientError("Telegram sendMessage response was not valid JSON.") from exc

        if not isinstance(response_json, dict):
            raise TelegramBotClientError("Telegram sendMessage response JSON must be an object.")

        if response_json.get("ok") is not True:
            raise TelegramBotClientError("Telegram sendMessage response was not ok.")

        return response_json
