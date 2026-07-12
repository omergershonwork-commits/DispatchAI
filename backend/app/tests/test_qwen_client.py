import json

import httpx
import pytest

from app.services.qwen_client import QwenClient, QwenClientError


def successful_qwen_response(text: str = "extracted incident json") -> dict:
    """Return a minimal successful OpenAI-compatible response payload."""

    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text,
                },
                "finish_reason": "stop",
            }
        ],
    }


def test_qwen_client_sends_expected_request_shape() -> None:
    """Verify Qwen client sends the expected chat completions request."""

    captured_request: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        """Capture the outgoing request and return a successful Qwen response."""

        captured_request["url"] = str(request.url)
        captured_request["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=successful_qwen_response("ok"))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = QwenClient(
        base_url="http://qwen.local",
        model_name="qwen-test",
        timeout_seconds=5,
        http_client=http_client,
    )

    response = client.generate("Extract the incident details.")

    assert captured_request["url"] == "http://qwen.local/v1/chat/completions"
    assert captured_request["payload"] == {
        "model": "qwen-test",
        "messages": [
            {
                "role": "user",
                "content": "Extract the incident details.",
            },
        ],
        "temperature": 0.1,
        "max_tokens": 1024,
    }
    assert response.model == "qwen-test"
    assert response.text == "ok"
    assert response.raw_response["choices"][0]["message"]["content"] == "ok"


def test_qwen_client_skips_default_headers_for_local_auto_mode() -> None:
    """Verify auto mode sends no tunnel headers to local Qwen endpoints."""

    captured_headers: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        """Capture headers sent to a local Qwen endpoint."""

        captured_headers["headers"] = request.headers
        return httpx.Response(200, json=successful_qwen_response("ok"))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = QwenClient(
        base_url="http://127.0.0.1:11434",
        model_name="qwen-test",
        timeout_seconds=5,
        headers_mode="auto",
        http_client=http_client,
    )

    client.generate("Extract the incident details.")

    assert "X-Pinggy-No-Screen" not in captured_headers["headers"]


def test_qwen_client_adds_pinggy_headers_for_remote_auto_mode() -> None:
    """Verify auto mode sends Pinggy bypass headers to remote Qwen endpoints."""

    captured_headers: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        """Capture headers sent to a remote Qwen endpoint."""

        captured_headers["headers"] = request.headers
        return httpx.Response(200, json=successful_qwen_response("ok"))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = QwenClient(
        base_url="https://qwen-remote.example",
        model_name="qwen-test",
        timeout_seconds=5,
        headers_mode="auto",
        http_client=http_client,
    )

    client.generate("Extract the incident details.")

    assert captured_headers["headers"]["X-Pinggy-No-Screen"] == "true"
    assert captured_headers["headers"]["User-Agent"] == "DispatchAI-dev-test"
    assert captured_headers["headers"]["Accept"] == "application/json"


def test_qwen_client_extra_headers_override_defaults() -> None:
    """Verify explicit extra headers can override default remote headers."""

    captured_headers: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        """Capture headers sent after extra-header merging."""

        captured_headers["headers"] = request.headers
        return httpx.Response(200, json=successful_qwen_response("ok"))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = QwenClient(
        base_url="https://qwen-remote.example",
        model_name="qwen-test",
        timeout_seconds=5,
        headers_mode="auto",
        extra_headers_json=json.dumps({"User-Agent": "Custom-Agent", "X-Test": "yes"}),
        http_client=http_client,
    )

    client.generate("Extract the incident details.")

    assert captured_headers["headers"]["User-Agent"] == "Custom-Agent"
    assert captured_headers["headers"]["X-Test"] == "yes"
    assert captured_headers["headers"]["X-Pinggy-No-Screen"] == "true"


def test_qwen_client_rejects_invalid_extra_headers_json() -> None:
    """Verify invalid extra header configuration fails clearly."""

    with pytest.raises(QwenClientError, match="QWEN_EXTRA_HEADERS_JSON"):
        QwenClient(extra_headers_json="not-json")


def test_qwen_client_rejects_invalid_headers_mode() -> None:
    """Verify unsupported header mode configuration fails clearly."""

    with pytest.raises(QwenClientError, match="QWEN_REQUEST_HEADERS_MODE"):
        QwenClient(headers_mode="always")


def test_qwen_client_rejects_empty_prompt() -> None:
    """Verify Qwen client fails fast when a prompt is empty."""

    client = QwenClient(http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))))

    with pytest.raises(ValueError, match="Prompt must not be empty"):
        client.generate("   ")


def test_qwen_client_raises_clear_error_on_timeout() -> None:
    """Verify Qwen client wraps transport timeouts in a domain-specific error."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Simulate a read timeout from the Qwen server."""

        raise httpx.ReadTimeout("request timed out", request=request)

    client = QwenClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(QwenClientError, match="timed out"):
        client.generate("Extract the incident details.")


def test_qwen_client_raises_clear_error_on_non_200_response() -> None:
    """Verify Qwen client reports non-success HTTP responses clearly."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Return a server error from the mocked Qwen endpoint."""

        return httpx.Response(500, json={"error": "model unavailable"}, request=request)

    client = QwenClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(QwenClientError, match="HTTP 500"):
        client.generate("Extract the incident details.")


def test_qwen_client_raises_clear_error_on_missing_assistant_text() -> None:
    """Verify Qwen client rejects malformed successful responses."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Return a 200 response that is missing assistant text."""

        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant"}}]}, request=request)

    client = QwenClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(QwenClientError, match="assistant text"):
        client.generate("Extract the incident details.")
