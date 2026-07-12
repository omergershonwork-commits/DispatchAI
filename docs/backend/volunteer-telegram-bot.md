# Volunteer Telegram bot

The backend supports a second Telegram bot for volunteer onboarding and dispatch lifecycle management.

## Webhook and token

| Setting | Value |
| --- | --- |
| Webhook path | `/webhooks/telegram/volunteers` |
| Bot token | `TELEGRAM_VOLUNTEER_BOT_TOKEN` |

The incident bot remains separate at `/webhooks/telegram` and uses `TELEGRAM_INCIDENT_BOT_TOKEN`.

## Registration flow

`/start`, `/register`, `register`, or `join` starts or resumes a persisted seven-step registration wizard.

The bot asks for:

1. full name
2. current city or service area
3. comma-separated skills
4. vehicle type
5. maximum travel distance in kilometers
6. phone number
7. whether the volunteer is available now

The draft is stored after every answer, so registration can continue after a restart or later message.

Until all steps are complete, the volunteer remains `inactive` and cannot receive a dispatch request.

Profile data used by matching is stored in `Volunteer.metadata_json`:

```json
{
  "registration_step": null,
  "registration_complete": true,
  "service_areas": ["Tel Aviv"],
  "location_text": "Tel Aviv",
  "skills": ["medical", "rescue", "transport"],
  "vehicle": "car",
  "max_distance_km": 20,
  "phone_number": "0501234567",
  "available_now": true
}
```

## Commands

| Command | Behavior |
| --- | --- |
| `/register` or `/start` | Start/resume registration, or reactivate a complete profile. |
| `/status` | Show the next missing registration step or the completed profile. |
| `/cancel` | Pause an incomplete registration. |
| `/stop` | Mark the volunteer inactive and stop new assignments. |
| `done` or `/done` | Mark the latest active dispatch complete and become available again. |

## Statuses

| Status | Meaning |
| --- | --- |
| `inactive` | Registration is incomplete, availability is false, or assignments are paused. |
| `available` | Registration is complete and the volunteer can be matched. |
| `busy` | The volunteer has an active dispatch. |

## Dispatch lifecycle

`VolunteerManagementService.create_dispatch_request(...)` now requires:

- a completed volunteer profile
- volunteer status `available`
- non-empty dispatch message text

It creates a `volunteer_dispatches` row and changes the volunteer to `busy`.

When the volunteer sends `done`, the latest `sent` dispatch becomes `done`, gets a completion timestamp, and the volunteer returns to `available`.

## Local setup

```powershell
cd D:\Projects\DispatchAI\DispatchAI\backend

$env:DATABASE_URL = "postgresql+psycopg://USERNAME:PASSWORD@HOST:5432/postgres"
$env:TELEGRAM_INCIDENT_BOT_TOKEN = "PASTE_INCIDENT_BOT_TOKEN"
$env:TELEGRAM_VOLUNTEER_BOT_TOKEN = "PASTE_VOLUNTEER_BOT_TOKEN"

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Register the volunteer bot webhook with the current public backend URL:

```powershell
$volunteerBotToken = $env:TELEGRAM_VOLUNTEER_BOT_TOKEN
$publicBackendUrl = "https://YOUR-CURRENT-TUNNEL.trycloudflare.com"
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

Send `/register` and answer all seven questions. Then run:

```sql
select id, source_chat_id, display_name, status, metadata_json
from volunteers
order by id desc
limit 5;
```

Expected: `registration_complete` is true and the matching fields are populated.
