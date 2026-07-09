from dataclasses import dataclass
import json
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import settings

DEFAULT_TEMPERATURE = 0.1
"""Default low-temperature setting used for deterministic backend extraction calls."""

DEFAULT_MAX_TOKENS = 1024
"""Default maximum number of generated tokens requested from Qwen."""

CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
"""OpenAI-compatible chat completions path exposed by the Qwen inference server."""

QWEN_HEADER_MODE_AUTO = "auto"
"""Automatically choose request headers based on whether Qwen is local or remote."""

QWEN_HEADER_MODE_NONE = "none"
"""Disable default Qwen request headers."""

QWEN_HEADER_MODE_PINGGY = "pinggy"
"""Force Pinggy-compatible bypass headers for Qwen requests."""

SUPPORTED_QWEN_HEADER_MODES = {
    QWEN_HEADER_MODE_AUTO,
    QWEN_HEADER_MODE_NONE,
    QWEN_HEADER_MODE_PINGGY,
}
"""Supported values for QWEN_REQUEST_HEADERS_MODE."""

LOCAL_QWEN_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal"}
"""Hostnames that should be treated as local Qwen endpoints."""

PINGGY_BYPASS_HEADERS = {
    "X-Pinggy-No-Screen": "true",
    "User-Agent": "DispatchAI-dev-test",
    "Accept": "application/json",
}
"""Headers required for Pinggy free tunnels to return API JSON instead of a caution page."""


class QwenClientError(RuntimeError):
    """Raised when the Qwen client cannot complete or parse an inference request."""


@dataclass(frozen=True)
class QwenGenerateResponse:
    """Normalized response returned by the Qwen client after generation."""

    model: str
    """Model name used for the generation request."""

    text: str
    """Assistant text extracted from the Qwen-compatible response."""

    raw_response: dict[str, Any]
    """Raw JSON response returned by the inference server."""


def is_local_qwen_url(base_url: str) -> bool:
    """Return whether a Qwen base URL points to a local endpoint."""

    parsed_url = urlparse(base_url)
    hostname = parsed_url.hostname
    if hostname is None:
        return False

    return hostname.lower() in LOCAL_QWEN_HOSTS


def parse_qwen_extra_headers(headers_json: str) -> dict[str, str]:
    """Parse optional Qwen extra headers from a JSON object string."""

    if not headers_json.strip():
        return {}

    try:
        raw_headers = json.loads(headers_json)
    except json.JSONDecodeError as exc:
        raise QwenClientError("QWEN_EXTRA_HEADERS_JSON must be a valid JSON object.") from exc

    if not isinstance(raw_headers, dict):
        raise QwenClientError("QWEN_EXTRA_HEADERS_JSON must be a JSON object.")

    parsed_headers: dict[str, str] = {}
    for key, value in raw_headers.items():
        if not isinstance(key, str) or not key.strip():
            raise QwenClientError("QWEN_EXTRA_HEADERS_JSON header names must be non-empty strings.")
        if not isinstance(value, str):
            raise QwenClientError("QWEN_EXTRA_HEADERS_JSON header values must be strings.")
        parsed_headers[key] = value

    return parsed_headers


def resolve_qwen_request_headers(base_url: str, headers_mode: str, extra_headers_json: str) -> dict[str, str]:
    """Resolve the headers that should be sent to the Qwen-compatible server."""

    normalized_mode = headers_mode.strip().lower()
    if normalized_mode not in SUPPORTED_QWEN_HEADER_MODES:
        raise QwenClientError(
            "QWEN_REQUEST_HEADERS_MODE must be one of: auto, none, pinggy."
        )

    if normalized_mode == QWEN_HEADER_MODE_NONE:
        request_headers: dict[str, str] = {}
    elif normalized_mode == QWEN_HEADER_MODE_PINGGY:
        request_headers = dict(PINGGY_BYPASS_HEADERS)
    elif is_local_qwen_url(base_url):
        request_headers = {}
    else:
        request_headers = dict(PINGGY_BYPASS_HEADERS)

    request_headers.update(parse_qwen_extra_headers(extra_headers_json))
    return request_headers


class QwenClient:
    """Small HTTP client for a Qwen-compatible chat completions server."""

    def __init__(
        self,
        base_url: str = settings.qwen_base_url,
        model_name: str = settings.qwen_model_name,
        timeout_seconds: float = settings.qwen_timeout_seconds,
        headers_mode: str = settings.qwen_request_headers_mode,
        extra_headers_json: str = settings.qwen_extra_headers_json,
        http_client: httpx.Client | None = None,
    ) -> None:
        """Create a Qwen client with injectable HTTP transport for tests."""

        self.base_url = base_url.rstrip("/")
        """Inference server base URL without a trailing slash."""

        self.model_name = model_name
        """Model name sent in each generation request."""

        self.timeout_seconds = timeout_seconds
        """Request timeout in seconds."""

        self.request_headers = resolve_qwen_request_headers(self.base_url, headers_mode, extra_headers_json)
        """Optional headers sent with every Qwen request."""

        self._http_client = http_client
        """Optional externally owned HTTP client used for tests or custom transports."""

    def generate(self, prompt: str) -> QwenGenerateResponse:
        """Send a prompt to Qwen and return normalized assistant text."""

        if not prompt.strip():
            raise ValueError("Prompt must not be empty.")

        payload = self._build_request_payload(prompt)
        raw_response = self._post_chat_completions(payload)
        text = self._extract_assistant_text(raw_response)

        return QwenGenerateResponse(
            model=self.model_name,
            text=text,
            raw_response=raw_response,
        )

    def _build_request_payload(self, prompt: str) -> dict[str, Any]:
        """Build an OpenAI-compatible chat completions payload for Qwen."""

        return {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": DEFAULT_TEMPERATURE,
            "max_tokens": DEFAULT_MAX_TOKENS,
        }

    def _post_chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Post the request payload to the Qwen chat completions endpoint."""

        url = f"{self.base_url}{CHAT_COMPLETIONS_PATH}"
        timeout = httpx.Timeout(self.timeout_seconds)
        headers = self.request_headers or None

        try:
            if self._http_client is not None:
                response = self._http_client.post(url, json=payload, headers=headers, timeout=timeout)
            else:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(url, json=payload, headers=headers)

            response.raise_for_status()
            response_json = response.json()
        except httpx.TimeoutException as exc:
            raise QwenClientError("Qwen request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise QwenClientError(f"Qwen request failed with HTTP {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            raise QwenClientError("Qwen request failed before a response was parsed.") from exc
        except ValueError as exc:
            raise QwenClientError("Qwen response was not valid JSON.") from exc

        if not isinstance(response_json, dict):
            raise QwenClientError("Qwen response JSON must be an object.")

        return response_json

    def _extract_assistant_text(self, raw_response: dict[str, Any]) -> str:
        """Extract assistant message text from an OpenAI-compatible response."""

        choices = raw_response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise QwenClientError("Qwen response did not contain choices.")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise QwenClientError("Qwen response choice must be an object.")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise QwenClientError("Qwen response choice did not contain a message object.")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise QwenClientError("Qwen response did not contain assistant text.")

        return content
