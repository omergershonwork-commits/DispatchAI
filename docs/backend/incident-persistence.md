# Incident persistence

The Telegram webhook can persist extracted incident reports into the database.

## Table

The backend creates an `incidents` ORM table in local/dev mode when the first incident write is attempted.

Stored fields include:

- `id`
- `source`
- `source_update_id`
- `source_message_id`
- `source_chat_id`
- `raw_text`
- `summary`
- `incident_type`
- `location_text`
- `urgency`
- `people_count`
- `contact_name`
- `phone_number`
- `needs`
- `confidence`
- `status`
- `metadata_json`
- `created_at`
- `updated_at`

## Statuses

| Status | Meaning |
| --- | --- |
| `pending_details` | The report is an incident, but critical details are missing. |
| `ready_for_dispatch` | The report has enough information for volunteer matching. |
| `dispatched` | Reserved for the future dispatch step. |
| `closed` | Reserved for resolved/manual closure. |

## Webhook behavior

For a Telegram text message:

1. Run incident extraction.
2. If extraction is actionable, create an incident with `ready_for_dispatch`.
3. If extraction needs more details, create a pending incident with `pending_details`.
4. If the same Telegram chat has a pending incident, merge the new extraction into that incident.
5. If the pending incident becomes complete, move it to `ready_for_dispatch`.
6. Send a Telegram reply.
7. Always return `202 Accepted` to Telegram unless the request shape is invalid.

## Webhook response metadata

The webhook response includes persistence metadata:

```text
incident_id
incident_created
incident_status
persistence_error
```

`persistence_error` uses a safe code:

```text
incident_persistence_unavailable
```

Raw database errors are not exposed to Telegram callers.

## Current limitation

There is no Alembic migration system yet. The persistence service calls SQLAlchemy `create_all` in local/dev flow before incident writes. A migration system should be added before production deployment.

## Manual verification

Run the backend with Postgres available, then send the Telegram bot a complete incident message.

Expected reply:

```text
Incident #<id> recorded.
...
This report is ready for dispatch matching.
```

Expected database state:

```sql
select id, source_chat_id, status, summary, location_text, needs
from incidents
order by id desc
limit 5;
```
