# DispatchAI

DispatchAI is an AI-assisted emergency coordination platform that converts unstructured incident reports into structured, actionable dispatch decisions.

A reporter can send a message through Telegram, the system extracts the incident type, urgency, location, affected people, and required assistance, then ranks eligible volunteers based on availability, skills, equipment, vehicle, reliability, response time, and geographic distance.

> DispatchAI is a coordination prototype. It does not replace official emergency services, dispatch centers, police, fire departments, medical services, or trained human operators.

## Why DispatchAI

During emergencies, coordination systems can become overloaded. Reports arrive in free text, locations can be unclear, volunteer availability changes quickly, and dispatchers must compare multiple candidates under time pressure.

DispatchAI reduces this operational burden by turning a message such as:

```text
There is a building fire near the mall in Nahariya.
One person is trapped and needs rescue.
```

into structured incident data and a ranked volunteer recommendation.

The system is designed around three principles:

1. **Understand the incident accurately**
2. **Exclude volunteers who are not actually eligible**
3. **Explain why a volunteer was selected or rejected**

## Core Features

- Telegram incident-reporting bot
- Telegram volunteer-management bot
- Qwen-based structured incident extraction
- Incident classification and urgency estimation
- GPS location support through Telegram
- Text-address geocoding
- Geographic distance calculation
- Hard volunteer travel-radius enforcement
- Skill-aware volunteer matching
- Equipment and vehicle-aware matching
- Availability and active-dispatch filtering
- Volunteer trust and response-time scoring
- Automatic dispatch offers through Telegram
- Offer timeout and acceptance lifecycle
- Incident and volunteer dashboard APIs
- Structured operational logging
- Deterministic dispatch scenario tests
- Live Qwen quality evaluation with a success-rate gate

## AMD Integration

DispatchAI uses a Qwen instruction model running in an AMD developer notebook environment.

The model is responsible for converting unstructured emergency messages into validated structured data such as:

- incident title
- summary
- incident type
- urgency
- affected-person description
- location
- requested assistance
- confidence
- missing information
- follow-up question

### Why strong AMD compute matters

This is not a simple text-classification task. Incident reports can be incomplete, multilingual, emotionally written, inconsistent, or spread across multiple messages.

The model must reason across the full report and avoid inventing missing facts. In a safety-related workflow, poor extraction can cause the wrong volunteer profile to be prioritized or an important detail to be missed.

We used the AMD notebook because larger reasoning-capable models require substantial VRAM and compute capacity. The AMD environment allowed us to run a stronger Qwen model rather than relying on a much smaller local model with weaker extraction quality.

The AI does not directly make irreversible emergency decisions. It produces structured recommendations that can be logged, tested, reviewed, and overridden by human operators.

## How It Works

```text
Reporter sends Telegram message or GPS location
                    |
                    v
        FastAPI Telegram webhook
                    |
                    v
          Qwen incident extraction
                    |
                    v
      Structured and validated incident
                    |
                    v
       Address geocoding or Telegram GPS
                    |
                    v
     Volunteer eligibility hard filters
                    |
                    v
      Weighted volunteer recommendation
                    |
                    v
       Telegram volunteer dispatch offer
                    |
                    v
       Accept / decline / timeout lifecycle
                    |
                    v
       Incident and dashboard state update
```

## Volunteer Eligibility

A volunteer is excluded before scoring when any required condition fails.

Examples:

- status is not `available`
- volunteer is busy
- volunteer already has a pending dispatch
- registration is incomplete
- coordinates are missing when geospatial enforcement is enabled
- calculated distance exceeds `max_distance_km`

This prevents a highly skilled but unavailable or distant volunteer from being selected.

## Matching Dimensions

Eligible volunteers are scored using scenario-specific weights.

The current matching dimensions are:

- location
- skill match
- estimated response time
- reliability
- inventory match
- vehicle match

The relative weights change by incident scenario.

Examples:

- medical emergencies emphasize medical skills and response time
- fires emphasize fire-response skills and protective equipment
- transport incidents emphasize vehicle suitability
- supply incidents emphasize required inventory
- evacuations emphasize vehicle capacity and logistics skills

## Supported Scenarios

The current configuration includes:

- medical emergencies
- security incidents
- disaster rescue
- fire response
- evacuation and shelter
- transport
- supplies
- general assistance

## Technology Stack

### Backend

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- PostGIS
- Pydantic

### AI

- Qwen instruction model
- OpenAI-compatible chat-completions API
- AMD developer notebook environment

### Messaging

- Telegram Bot API

### Infrastructure

- Docker
- Docker Compose
- GitHub Actions

### Location

- Telegram GPS messages
- Nominatim-compatible geocoding
- Haversine distance calculation

## Repository Structure

```text
DispatchAI/
├── backend/
│   ├── app/
│   │   ├── api/                 # FastAPI routes and Telegram webhooks
│   │   ├── core/                # Configuration and logging
│   │   ├── db/                  # Database session and schema migration helpers
│   │   ├── evaluations/         # Live Qwen evaluation cases and scoring
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic contracts
│   │   ├── services/            # Extraction, matching, dispatch, geocoding
│   │   └── tests/               # Unit, integration, and dispatch scenario tests
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
└── README.md
```

## Current Docker Setup

The repository currently includes containers for:

- PostgreSQL with PostGIS
- FastAPI backend

The Qwen model runs externally in the AMD notebook and is accessed through a configurable OpenAI-compatible endpoint.

A complete `.env.example` and final container configuration will be added before release.

## Configuration

The backend uses environment variables.

### Core

```text
APP_NAME
ENVIRONMENT
DATABASE_URL
LOG_LEVEL
```

### Qwen

```text
QWEN_BASE_URL
QWEN_MODEL_NAME
QWEN_TIMEOUT_SECONDS
QWEN_REQUEST_HEADERS_MODE
QWEN_EXTRA_HEADERS_JSON
```

### Telegram

```text
TELEGRAM_INCIDENT_BOT_TOKEN
TELEGRAM_VOLUNTEER_BOT_TOKEN
TELEGRAM_API_BASE_URL
TELEGRAM_TIMEOUT_SECONDS
```

### Geocoding

```text
GEOCODING_ENABLED
GEOCODING_BASE_URL
GEOCODING_USER_AGENT
GEOCODING_TIMEOUT_SECONDS
GEOCODING_COUNTRY_CODES
```

### Dispatch Lifecycle

```text
DISPATCH_OFFER_TIMEOUT_SECONDS
DISPATCH_TIMEOUT_POLL_SECONDS
```

Do not commit real tokens, passwords, or private endpoint credentials.

## Local Development

### Requirements

- Python 3.12+
- Docker
- Docker Compose
- PostgreSQL/PostGIS, or Docker Compose
- Telegram bot tokens for live Telegram tests
- accessible Qwen endpoint for live model inference

### Start the database and backend

```bash
docker compose up --build
```

### Verify services

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### Run backend tests

```bash
cd backend
python -m pip install -r requirements.txt
pytest -q
```

## Telegram Demo Flow

### 1. Register volunteers

Each volunteer provides:

- name
- service area
- skills
- vehicle
- maximum travel distance
- contact number
- availability

The volunteer then shares a Telegram GPS location.

### 2. Submit an incident

Example:

```text
There is a building fire near the mall in Nahariya.
One person is trapped. We need firefighters and rescue support.
```

The reporter can also send a Telegram location.

### 3. AI extraction

Qwen creates a structured incident containing:

```json
{
  "title": "Building Fire",
  "incident_type": "fire",
  "urgency": "critical",
  "location_text": "Nahariya, near the mall",
  "casualties_text": "One person trapped",
  "needs": ["fire response", "rescue"]
}
```

### 4. Matching

The matcher:

1. removes unavailable volunteers
2. removes busy volunteers
3. removes volunteers with pending offers
4. calculates actual distance
5. enforces maximum travel radius
6. applies scenario-specific matching weights
7. ranks the remaining volunteers

### 5. Dispatch

The selected volunteer receives a Telegram offer containing:

- title
- location
- estimated distance
- summary
- urgency
- affected people
- required help

The volunteer can reply:

```text
accept
```

or:

```text
decline
```

## Dashboard API

Current dashboard endpoints include:

```text
GET   /dashboard/incidents
GET   /dashboard/incidents/{incident_id}
GET   /dashboard/volunteers
GET   /dashboard/volunteers/{volunteer_id}
PATCH /dashboard/volunteers/{volunteer_id}
```

Health endpoints:

```text
GET /health
GET /ready
```

## Testing Strategy

### Deterministic backend tests

The standard CI suite covers:

- extraction parsing
- incident persistence
- volunteer registration
- scenario classification
- weighted matching
- unavailable-volunteer exclusion
- busy-volunteer exclusion
- pending-response exclusion
- travel-radius exclusion
- Telegram dispatch creation
- database state transitions
- Docker build and startup
- health and readiness checks

### End-to-end dispatch scenarios

The repository includes multiple realistic dispatch scenarios covering:

- medical
- fire
- rescue
- security
- evacuation
- transport
- supplies
- general assistance
- no eligible volunteer

The tests verify that the strongest unavailable volunteer is skipped and the strongest eligible volunteer is selected.

### Live Qwen quality gate

A separate GitHub Actions job runs live evaluation cases against the configured Qwen endpoint.

The evaluation checks:

- schema validity
- incident classification
- incident type
- urgency
- location
- needs
- affected-person extraction
- confidence range
- title quality
- create or follow-up decision

The current CI gate requires:

```text
Success Rate > 90%
```

For 20 cases:

```text
18/20 = 90%  -> fail
19/20 = 95%  -> pass
20/20 = 100% -> pass
```

Live evaluation results are uploaded as GitHub Actions artifacts.

## Logging and Explainability

DispatchAI emits structured logs for important decisions.

Examples:

```text
geocoding_started
geocoding_succeeded
volunteer_excluded reason=missing_coordinates
volunteer_excluded reason=outside_travel_radius
volunteer_eligible
geospatial_matching_completed
automatic_dispatch_offer_sent
```

This makes it possible to audit why a volunteer was selected or rejected.

## Safety and Limitations

DispatchAI is an experimental coordination system.

Current limitations include:

- AI output can be incorrect or incomplete
- geocoded addresses can be approximate
- GPS data can become stale
- Haversine distance is not road travel time
- external model and geocoding services can become unavailable
- current dispatch flow sends one offer at a time
- dashboard authentication and role-based access control are not complete
- official emergency-service integration is not implemented

Before real-world deployment, the system would require:

- trained human review
- formal security testing
- webhook authentication
- dashboard authentication and authorization
- encrypted sensitive data
- audit retention policies
- redundant infrastructure
- real routing and estimated-arrival-time services
- location freshness enforcement
- legal and emergency-service approval

## Roadmap

- volunteer GPS freshness enforcement
- top-three parallel offers
- first-acceptance-wins transaction handling
- cancellation of remaining offers
- real driving-time routing
- dispatcher assignment and reassignment controls
- dashboard authentication and RBAC
- audit trail and operational analytics
- multilingual extraction evaluation
- resilient Qwen deployment
- full production containerization

## Hackathon Demo Story

The recommended demo shows:

1. two or more volunteers registered
2. one volunteer unavailable or outside the allowed radius
3. a reporter sends an emergency message
4. Qwen extracts the structured incident
5. the matcher excludes the ineligible volunteer
6. the best eligible volunteer receives an offer
7. the volunteer accepts
8. the incident and volunteer statuses update
9. logs explain the dispatch decision

## Team

DispatchAI was built for the AMD Developer Hackathon: Act II.

## License

A project license will be added before final public release.
