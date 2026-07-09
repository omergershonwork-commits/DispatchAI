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
