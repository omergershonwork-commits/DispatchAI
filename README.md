# DispatchAI

AI-assisted incident intake and volunteer dispatch for high-pressure emergency coordination.

DispatchAI receives incident reports through Telegram, uses Qwen to extract structured incident data, applies deterministic eligibility rules, ranks suitable volunteers, and manages the dispatch lifecycle through Telegram and dashboard APIs.

> **Safety notice**  
> DispatchAI is a coordination platform and hackathon prototype. It does not replace official emergency services, trained dispatchers, police, fire departments, medical services, or human approval in safety-critical operations.

## Product Summary

Emergency reports are often incomplete, multilingual, emotional, or spread across multiple messages. DispatchAI reduces the operational burden by turning those reports into validated incident records and explainable volunteer recommendations.

The platform is designed around three principles:

1. Understand the incident accurately.
2. Exclude responders who are unavailable or ineligible.
3. Explain why a responder was selected or rejected.

## Core Capabilities

- Telegram incident-reporting bot
- Telegram volunteer registration and status management
- Qwen-based structured incident extraction
- Multi-message incident context
- Incident type and urgency classification
- Telegram GPS support
- Text-address geocoding
- Haversine distance calculation
- Hard travel-radius enforcement
- Skill, inventory, vehicle, response-time, and reliability scoring
- Automatic Telegram dispatch offers
- Accept, decline, timeout, and completion lifecycle
- Incident and volunteer dashboard APIs
- Structured operational logs
- Deterministic end-to-end dispatch tests
- Docker and GitHub Actions validation

## AMD Integration

DispatchAI runs its Qwen instruction model in an AMD developer notebook environment.

The model converts unstructured reports into a validated schema containing:

- title and summary
- incident type
- urgency
- location
- affected-person description
- requested assistance
- confidence
- missing fields
- follow-up question

### Why AMD compute matters

Incident understanding is more demanding than simple classification. Reports can contain uncertainty, corrections, mixed languages, missing details, and several facts that must be reconciled.

The AMD notebook provides the VRAM and compute capacity required to run a stronger reasoning-capable Qwen model. This improves extraction quality compared with using a significantly smaller local model.

The model does not directly execute irreversible actions. Its output is validated, persisted, logged, and passed into deterministic eligibility and matching rules that can be reviewed or overridden by operators.

## Architecture

```text
Reporter / Volunteer
        |
        v
Telegram Bot API
        |
        v
FastAPI webhook layer
        |
        +---------------------------+
        |                           |
        v                           v
Qwen incident extraction     Volunteer management
        |                           |
        +-------------+-------------+
                      |
                      v
            PostgreSQL + PostGIS
                      |
                      v
          Geospatial eligibility filter
                      |
                      v
       Scenario-specific weighted ranking
                      |
                      v
            Telegram dispatch offer
                      |
                      v
       Accept / decline / timeout / done
```

## Volunteer Selection

Volunteer selection is split into two stages.

### Hard eligibility filters

A volunteer is excluded before scoring when:

- status is not `available`
- registration is incomplete
- the volunteer is busy
- an open dispatch already exists
- coordinates are missing while geospatial matching is enabled
- `max_distance_km` is missing or invalid
- calculated distance exceeds the allowed radius

A highly skilled but unavailable or distant volunteer is therefore never selected.

### Weighted ranking

Eligible volunteers are ranked by:

- location
- skill match
- estimated response time
- reliability
- inventory match
- vehicle match

Weights vary by scenario. Medical incidents emphasize medical skills and response time, while transport and evacuation incidents place more weight on vehicle suitability.

## Supported Scenarios

- medical emergency
- security incident
- disaster rescue
- fire response
- evacuation and shelter
- transport
- supplies
- general assistance

## Technology Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy, Pydantic
- **Database:** PostgreSQL, PostGIS
- **AI:** Qwen, OpenAI-compatible chat-completions API
- **Compute:** AMD developer notebook environment
- **Messaging:** Telegram Bot API
- **Location:** Telegram GPS, Nominatim-compatible geocoding
- **Infrastructure:** Docker, Docker Compose, GitHub Actions

## Repository Layout

```text
DispatchAI/
├── backend/
│   ├── app/
│   │   ├── api/          # REST endpoints and Telegram webhooks
│   │   ├── core/         # Configuration and logging
│   │   ├── db/           # Database session and schema helpers
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic contracts
│   │   ├── services/     # Extraction, matching, dispatch, geocoding
│   │   └── tests/        # Unit and integration tests
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
└── README.md
```

## Configuration

Configuration is supplied through environment variables. Never commit real tokens or credentials.

### Application

| Variable | Required | Description |
|---|---:|---|
| `APP_NAME` | No | Service name |
| `ENVIRONMENT` | No | Runtime environment |
| `DATABASE_URL` | Yes | PostgreSQL connection URL |
| `LOG_LEVEL` | No | Logging level, default `INFO` |

### Qwen

| Variable | Required | Description |
|---|---:|---|
| `QWEN_BASE_URL` | Yes for live AI | AMD-hosted OpenAI-compatible endpoint |
| `QWEN_MODEL_NAME` | Yes for live AI | Served Qwen model identifier |
| `QWEN_TIMEOUT_SECONDS` | No | Request timeout |
| `QWEN_REQUEST_HEADERS_MODE` | No | `auto`, `none`, or `pinggy` |
| `QWEN_EXTRA_HEADERS_JSON` | No | Additional headers as JSON |

### Telegram

| Variable | Required | Description |
|---|---:|---|
| `TELEGRAM_INCIDENT_BOT_TOKEN` | Yes for incident bot | Incident bot token |
| `TELEGRAM_VOLUNTEER_BOT_TOKEN` | Yes for volunteer bot | Volunteer bot token |
| `TELEGRAM_API_BASE_URL` | No | Telegram API base URL |
| `TELEGRAM_TIMEOUT_SECONDS` | No | Telegram request timeout |

### Geocoding and dispatch

| Variable | Required | Description |
|---|---:|---|
| `GEOCODING_ENABLED` | No | Enable address geocoding |
| `GEOCODING_BASE_URL` | No | Nominatim-compatible endpoint |
| `GEOCODING_USER_AGENT` | When enabled | Identifying user agent |
| `GEOCODING_COUNTRY_CODES` | No | Country restriction, for example `il` |
| `DISPATCH_OFFER_TIMEOUT_SECONDS` | No | Offer timeout |
| `DISPATCH_TIMEOUT_POLL_SECONDS` | No | Timeout worker interval |

## Run with Docker

### Prerequisites

- Docker Engine
- Docker Compose
- reachable Qwen endpoint for live extraction
- Telegram bot tokens for live Telegram flows

### Start

```bash
docker compose up --build -d
```

### Verify

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### Logs

```bash
docker compose logs -f backend
```

### Stop

```bash
docker compose down --remove-orphans
```

To remove development database volumes:

```bash
docker compose down -v --remove-orphans
```

## Local Development

```bash
cd backend
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
pytest -q
```

## API Endpoints

Health:

```text
GET /health
GET /ready
```

Dashboard:

```text
GET   /dashboard/incidents
GET   /dashboard/incidents/{incident_id}
GET   /dashboard/volunteers
GET   /dashboard/volunteers/{volunteer_id}
PATCH /dashboard/volunteers/{volunteer_id}
```

## Demo Flow

1. Register volunteers through the volunteer bot.
2. Set skills, vehicle, maximum travel distance, and availability.
3. Share a Telegram GPS location.
4. Submit an incident through the incident bot.
5. Qwen extracts type, urgency, location, casualties, and required help.
6. The backend excludes unavailable and out-of-range volunteers.
7. The best eligible volunteer receives the offer.
8. The volunteer replies `accept`, `decline`, or `done`.
9. Incident and volunteer state are updated in the database and dashboard.

## Testing and CI

The required CI pipeline runs:

1. backend dependency installation
2. backend tests
3. Docker image build
4. database and backend startup
5. `/health` verification
6. `/ready` verification
7. stack cleanup

The deterministic dispatch suite covers:

- medical, fire, rescue, security, evacuation, transport, supplies, and general assistance
- unavailable, busy, and pending-response exclusion
- out-of-range exclusion
- no-eligible-volunteer behavior
- recommendation persistence
- Telegram offer creation
- volunteer state transitions

Live model evaluation is kept outside the required CI path because the AMD notebook endpoint is external and may not be continuously available.

## Observability

Structured logs include:

```text
geocoding_started
geocoding_succeeded
volunteer_excluded reason=missing_coordinates
volunteer_excluded reason=outside_travel_radius
volunteer_eligible
geospatial_matching_completed
automatic_dispatch_offer_sent
```

These logs provide an audit trail for matching and dispatch decisions.

## Security and Production Hardening

The current implementation validates model output, enforces availability server-side, stores dispatch state transitions, and keeps credentials outside source code.

Before deployment in a real emergency environment, complete:

- signed and authenticated webhooks
- dashboard authentication and role-based access control
- TLS termination
- managed secret storage
- encrypted sensitive data
- backup and restore procedures
- formal security testing
- audit retention and privacy policies
- human approval rules for safety-critical dispatch

## Deployment Recommendations

For an internet-facing environment:

- run PostgreSQL/PostGIS as a managed or backed-up service
- place the API behind a TLS-enabled reverse proxy or load balancer
- restrict dashboard endpoints to authorized operators
- centralize logs and alerts
- monitor health, readiness, model latency, Telegram failures, and dispatch errors
- use immutable image tags and a rollback-capable deployment process
- maintain separate development, staging, and production environments

## Current Limitations

- AI extraction can be incomplete or incorrect
- geocoded addresses can be approximate
- GPS positions can become stale
- Haversine distance is not road travel time
- the AMD notebook and geocoding service are external dependencies
- the current dispatch flow sends one offer at a time
- production authentication and authorization are not yet complete
- official emergency-service integrations are not included

## Roadmap

- volunteer location freshness enforcement
- road-route travel-time estimation
- parallel top-candidate offers with atomic first acceptance
- dispatcher assignment and reassignment controls
- webhook signature verification
- dashboard RBAC
- managed secrets and deployment manifests
- operational metrics and alerting

## License

Add the project license before public distribution or reuse.
