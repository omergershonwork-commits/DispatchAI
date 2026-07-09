# Incident persistence

The backend can persist extracted incident reports from any inbound source that can provide source metadata and raw text.

## Source adapter boundary

Persistence is source-agnostic. Source-specific webhook code, such as Telegram, translates an inbound event into `SourceIncidentContext` before calling the persistence service.

`SourceIncidentContext` contains:

- `source`
- `source_update_id`
- `source_message_id`
- `source_chat_id`
- `raw_text`

This keeps future sources, such as WhatsApp, SMS, web forms, or voice transcripts, outside the persistence service. Each source should add its own adapter and reuse the same persistence contract.

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
2. Build generic `SourceIncidentContext` from the Telegram update.
3. If extraction is actionable, create an incident with `ready_for_dispatch`.
4. If extraction needs more details, create a pending incident with `pending_details`.
5. If the same source conversation has a pending incident, merge the new extraction into that incident.
6. If the pending incident becomes complete, move it to `ready_for_dispatch`.
7. Send a Telegram reply.
8. Always return `202 Accepted` to Telegram unless the request shape is invalid.

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
