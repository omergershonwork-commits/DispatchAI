# Volunteer Telegram bot

The backend supports a second Telegram bot for volunteer management.

## Purpose

The incident bot receives emergency reports from people who need help. The volunteer bot manages volunteers separately.

The volunteer bot currently supports:

- volunteer registration
- volunteer status checks
- volunteer inactive/stop command
- marking the latest active dispatch as done
- storing dispatch request lifecycle state

## Runtime variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `TELEGRAM_INCIDENT_BOT_TOKEN` | `TELEGRAM_BOT_TOKEN` | Incident-report bot token used by `/webhooks/telegram`. |
| `TELEGRAM_VOLUNTEER_BOT_TOKEN` | empty | Volunteer-management bot token used by `/webhooks/telegram/volunteers`. |
| `TELEGRAM_API_BASE_URL` | `https://api.telegram.org` | Telegram Bot API base URL. |
| `TELEGRAM_TIMEOUT_SECONDS` | `10` | HTTP timeout for Telegram send-message calls. |

`TELEGRAM_BOT_TOKEN` remains as a legacy fallback for the incident bot.

## Webhook paths

| Bot | Webhook path |
| --- | --- |
| Incident bot | `/webhooks/telegram` |
| Volunteer bot | `/webhooks/telegram/volunteers` |

Each Telegram bot must be registered with its own webhook URL.

## Volunteer commands

| Command | Behavior |
| --- | --- |
| `/start` | Register or reactivate the volunteer. |
| `/register` | Register or reactivate the volunteer. |
| `register` | Register or reactivate the volunteer. |
| `/status` | Return current volunteer status. |
| `status` | Return current volunteer status. |
| `done` | Mark the latest active dispatch as complete. |
| `/done` | Mark the latest active dispatch as complete. |
| `/stop` | Mark volunteer inactive. |
| `stop` | Mark volunteer inactive. |

## Tables

### `volunteers`

Stores a registered volunteer profile:

- `id`
- `source`
- `source_chat_id`
- `source_user_id`
- `source_username`
- `first_name`
- `last_name`
- `display_name`
- `status`
- `metadata_json`
- `registered_at`
- `last_seen_at`
- `updated_at`

Volunteer rows are unique by `source` and `source_chat_id`.

### `volunteer_dispatches`

Stores dispatch requests sent to volunteers:

- `id`
- `volunteer_id`
- `incident_id`
- `message_text`
- `status`
- `sent_at`
- `completed_at`
- `metadata_json`
- `created_at`
- `updated_at`

## Statuses

### Volunteer statuses

| Status | Meaning |
| --- | --- |
| `available` | Registered and can receive dispatch requests. |
| `busy` | Has an active dispatch request. |
| `inactive` | Registered but should not receive dispatch requests. |

### Dispatch statuses

| Status | Meaning |
| --- | --- |
| `sent` | Dispatch request was created for a volunteer. |
| `done` | Volunteer sent `done` or `/done`. |
| `cancelled` | Reserved for future cancellation flow. |

## Dispatch sending contract

`VolunteerManagementService.create_dispatch_request(...)` creates a dispatch record and marks the volunteer `busy`. It returns source metadata and message text so a channel adapter can send the message through the correct bot.

For Telegram volunteers, the future matcher/dispatcher should:

1. Select a volunteer row.
2. Call `create_dispatch_request(...)` with the incident id and message text.
3. Send `result.message_text` to `result.source_chat_id` using `TELEGRAM_VOLUNTEER_BOT_TOKEN`.
4. Wait for `done` from `/webhooks/telegram/volunteers`.

## Local setup

Start the backend with both bot tokens:

```powershell
cd D:\Projects\DispatchAI\DispatchAI\backend

$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/ai_rescue"
$env:TELEGRAM_INCIDENT_BOT_TOKEN = "PASTE_INCIDENT_BOT_TOKEN_HERE"
$env:TELEGRAM_VOLUNTEER_BOT_TOKEN = "PASTE_VOLUNTEER_BOT_TOKEN_HERE"

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Expose the backend:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Register the volunteer bot webhook:

```powershell
$volunteerBotToken = $env:TELEGRAM_VOLUNTEER_BOT_TOKEN
$publicBackendUrl = "https://YOUR-TUNNEL.trycloudflare.com"
$webhookUrl = "$publicBackendUrl/webhooks/telegram/volunteers"

$body = @{
  url = $webhookUrl
  allowed_updates = @("message")
  drop_pending_updates = $true
} | ConvertTo-Json -Depth 10

Invoke-RestMethod `
  -Uri "https://api.telegram.org/bot$volunteerBotToken/setWebhook" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

## Manual verification

Send the volunteer bot:

```text
/register
```

Expected reply:

```text
Volunteer registered. You will receive dispatch messages here when help is needed.
```

Check database:

```sql
select id, source, source_chat_id, status, display_name
from volunteers
order by id desc
limit 5;
```

After a dispatch record exists, send:

```text
done
```

Expected reply:

```text
Dispatch #<id> marked done. Thank you.
```
