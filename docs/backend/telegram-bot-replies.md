# Telegram bot replies

The backend can accept Telegram webhook messages, persist incident reports, and send plain-text replies with the Telegram Bot API.

## Runtime variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | empty | BotFather token used to send replies. Must not be committed. |
| `TELEGRAM_API_BASE_URL` | `https://api.telegram.org` | Telegram Bot API base URL. |
| `TELEGRAM_TIMEOUT_SECONDS` | `10` | HTTP timeout for Telegram send-message calls. |

## Local setup

Start the backend with Qwen, Telegram, and database variables set:

```powershell
cd D:\Projects\DispatchAI\DispatchAI\backend

$env:QWEN_BASE_URL = "https://ovaqv-80-230-79-87.run.pinggy-free.link"
$env:QWEN_MODEL_NAME = "qwen2:0.5b"
$env:QWEN_TIMEOUT_SECONDS = "60"
$env:QWEN_REQUEST_HEADERS_MODE = "auto"
$env:QWEN_EXTRA_HEADERS_JSON = ""

$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/ai_rescue"
$env:TELEGRAM_BOT_TOKEN = "PASTE_TOKEN_HERE"
$env:TELEGRAM_TIMEOUT_SECONDS = "10"

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Expose the local backend through a public HTTPS tunnel:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Register the Telegram webhook:

```powershell
$publicBackendUrl = "https://YOUR-TUNNEL.trycloudflare.com"
$webhookUrl = "$publicBackendUrl/webhooks/telegram"

$body = @{
  url = $webhookUrl
  allowed_updates = @("message")
  drop_pending_updates = $true
} | ConvertTo-Json -Depth 10

Invoke-RestMethod `
  -Uri "https://api.telegram.org/bot$($env:TELEGRAM_BOT_TOKEN)/setWebhook" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

Check the webhook status:

```powershell
Invoke-RestMethod `
  -Uri "https://api.telegram.org/bot$($env:TELEGRAM_BOT_TOKEN)/getWebhookInfo" `
  -Method GET
```

## Reply behavior

For text messages, the webhook now attempts extraction, persistence, and Telegram reply sending.

- If extraction succeeds and the incident is actionable, the bot replies with the persisted incident id and a short incident summary.
- If extraction succeeds but needs more details, the bot persists/updates a pending incident and replies with the follow-up question.
- If extraction fails, the bot replies with a safe clarification request.
- If persistence fails, the bot replies with a safe resend request.
- If Telegram reply sending fails, the webhook still returns `202 Accepted` so Telegram does not retry indefinitely.

The webhook response includes:

```text
incident_id
incident_created
incident_status
persistence_error
telegram_reply_sent
telegram_reply_error
```

## Manual verification

Send the bot a message like:

```text
My name is Omer. My phone number is 0501234567. There is a car accident near Dizengoff Center. Two people are injured and need medical help.
```

Expected local signs:

```text
POST /webhooks/telegram 202 Accepted
```

Expected Telegram behavior:

```text
Incident #<id> recorded.
...
This report is ready for dispatch matching.
```

Expected database check:

```sql
select id, source_chat_id, status, summary, location_text, needs
from incidents
order by id desc
limit 5;
```

## Safety and secrets

Do not commit the Telegram bot token. Keep it in environment variables only.
