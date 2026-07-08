# Qwen Client Implementation Plan

## Goal

Create a backend service layer that can call a local Qwen-compatible inference server without coupling Telegram webhook ingestion directly to the model runtime.

## First implementation slice

The first Qwen task should add only the client skeleton and tests. It should not extract incidents, write to the database, dispatch volunteers, or expose a public endpoint.

## Proposed files

```text
backend/app/services/__init__.py
backend/app/services/qwen_client.py
backend/app/tests/test_qwen_client.py
```

## Configuration variables

```text
QWEN_BASE_URL
QWEN_MODEL_NAME
QWEN_TIMEOUT_SECONDS
```

These values should be added to `backend/app/core/config.py` so deployment can point the backend at a local or remote Qwen-compatible inference server.

## Client contract

The service should expose a small client class with one method:

```python
class QwenClient:
    def generate(self, prompt: str) -> QwenGenerateResponse:
        ...
```

The response object should include:

```text
model
text
raw_response
```

## HTTP behavior

The client should use a Qwen-compatible HTTP endpoint through `httpx`. The first version should target an OpenAI-compatible chat completions endpoint because many local inference servers expose that shape.

The request should contain:

```text
model
messages
temperature
max_tokens
```

## Testing strategy

Tests must not require a real Qwen server. Use mocking to verify:

```text
The client sends the expected request shape.
The client parses a successful response.
The client raises a clear error on timeout or non-200 response.
```

## Later tasks

After the client skeleton is stable, separate tasks should add:

```text
Prompt templates for incident extraction.
Strict JSON parsing and validation.
Telegram webhook to Qwen pipeline wiring.
Database persistence for extracted incidents.
Dispatch candidate selection.
```

## Non-goals for the first Qwen task

```text
No real model deployment.
No incident extraction prompt.
No database writes.
No dispatch logic.
No frontend.
No Telegram webhook side effects.
```
