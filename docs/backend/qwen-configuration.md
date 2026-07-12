# Qwen configuration

The backend calls a Qwen-compatible OpenAI chat completions endpoint at:

```text
{QWEN_BASE_URL}/v1/chat/completions
```

Do not include `/v1` in `QWEN_BASE_URL`.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `QWEN_BASE_URL` | `http://localhost:8001` | Base URL for the Qwen-compatible server. |
| `QWEN_MODEL_NAME` | `qwen` | Model name sent in the chat completions payload. |
| `QWEN_TIMEOUT_SECONDS` | `30` | HTTP timeout for Qwen requests. |
| `QWEN_REQUEST_HEADERS_MODE` | `auto` | Header mode: `auto`, `none`, or `pinggy`. |
| `QWEN_EXTRA_HEADERS_JSON` | empty | Optional JSON object of additional headers. |

## Header modes

### `auto`

Recommended default.

- Local Qwen URLs send no Pinggy headers.
- Remote Qwen URLs send Pinggy bypass headers automatically.

Local hosts are:

```text
localhost
127.0.0.1
0.0.0.0
::1
host.docker.internal
```

Remote URLs receive these default headers:

```text
X-Pinggy-No-Screen: true
User-Agent: DispatchAI-dev-test
Accept: application/json
```

### `none`

Do not send default Pinggy headers. Use this for normal remote servers that do not need tunnel bypass headers.

### `pinggy`

Always send Pinggy bypass headers, even if the base URL is local.

## Current remote Pinggy setup

```powershell
$env:QWEN_BASE_URL = "https://etlpt-80-230-79-87.run.pinggy-free.link"
$env:QWEN_MODEL_NAME = "qwen2:0.5b"
$env:QWEN_TIMEOUT_SECONDS = "60"
$env:QWEN_REQUEST_HEADERS_MODE = "auto"
$env:QWEN_EXTRA_HEADERS_JSON = ""
```

Because the URL is remote, `auto` adds the Pinggy bypass headers.

## Future local Ollama setup

```powershell
$env:QWEN_BASE_URL = "http://127.0.0.1:11434"
$env:QWEN_MODEL_NAME = "qwen2:0.5b"
$env:QWEN_TIMEOUT_SECONDS = "60"
$env:QWEN_REQUEST_HEADERS_MODE = "auto"
$env:QWEN_EXTRA_HEADERS_JSON = ""
```

Because the URL is local, `auto` sends no Pinggy headers.

## Custom headers

Use `QWEN_EXTRA_HEADERS_JSON` only when a server or tunnel needs additional headers.

Example:

```powershell
$env:QWEN_EXTRA_HEADERS_JSON = '{"Authorization":"Bearer dev-token"}'
```

Do not commit real secrets to the repository.

## Verification

Test the model directly:

```powershell
$body = @{
  model = $env:QWEN_MODEL_NAME
  messages = @(
    @{
      role = "user"
      content = "Return only this JSON: {""ok"":true}"
    }
  )
  temperature = 0.1
  max_tokens = 64
} | ConvertTo-Json -Depth 10

Invoke-RestMethod `
  -Uri "$env:QWEN_BASE_URL/v1/chat/completions" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{
    "X-Pinggy-No-Screen" = "true"
    "User-Agent" = "DispatchAI-dev-test"
    "Accept" = "application/json"
  } `
  -Body $body
```

Then start the backend in a terminal where the same environment variables are set:

```powershell
cd D:\Projects\DispatchAI\DispatchAI\backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Send a mock Telegram webhook. A working Qwen setup should return populated `extraction` data and an empty `extraction_error`.
