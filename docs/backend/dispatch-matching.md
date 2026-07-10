# Dispatch matching

The backend can generate ranked volunteer recommendations for an incident without sending volunteer messages automatically.

## Flow

```text
ready incident
→ select dispatch scenario
→ score available volunteers
→ persist top recommendations
→ return ranked results
```

## Endpoint

```text
POST /dispatch/incidents/{incident_id}/recommendations?limit=3
```

The endpoint returns the selected scenario, scenario confidence, and the persisted recommendation rows.

It does not send Telegram messages to volunteers. The future dispatch step should convert one or more recommendations into `VolunteerDispatch` rows and send messages through the volunteer bot.

## Scenario config

Scenario presets live in:

```text
backend/app/config/dispatch_scenarios.json
```

Current scenarios:

- `medical_urgent`
- `transport`
- `supplies`
- `general_assistance`

Each scenario contains:

- `description`
- `keywords`
- `urgencies`
- `weights`
- `preferred_skills`

Weights are normalized at runtime, so each scenario is deterministic and testable.

## Scoring dimensions

Volunteer score is calculated from:

| Dimension | Source |
| --- | --- |
| `location` | Incident `location_text` versus volunteer `metadata_json.service_areas`. |
| `availability` | Only `available` volunteers are considered; score is `1.0`. |
| `skill_match` | Incident type/needs and scenario skills versus volunteer `metadata_json.skills`. |
| `response_time` | Volunteer `metadata_json.response_time_minutes`. |
| `reliability` | Volunteer `metadata_json.reliability_score`. |

Example volunteer metadata:

```json
{
  "skills": ["medical", "first_aid"],
  "service_areas": ["Dizengoff Center", "Tel Aviv"],
  "response_time_minutes": 8,
  "reliability_score": 0.9
}
```

## Recommendation persistence

Recommendations are stored in:

```text
dispatch_recommendations
```

Stored fields include:

- `id`
- `incident_id`
- `volunteer_id`
- `scenario`
- `rank`
- `total_score`
- `score_breakdown`
- `status`
- `created_at`
- `updated_at`

Current status:

```text
recommended
```

Future statuses are reserved for conversion into actual volunteer dispatch messages.

## Manual verification

Create or use a ready incident and available volunteers, then run:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/dispatch/incidents/1/recommendations?limit=3" `
  -Method POST
```

Expected database check:

```sql
select incident_id, volunteer_id, scenario, rank, total_score, score_breakdown
from dispatch_recommendations
where incident_id = 1
order by rank asc;
```
