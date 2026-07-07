# Tasks

## Phase 0 — Project context and repo setup
Goal: create the source documents and basic project structure.
- [x] Create repo structure.
- [x] Add `NORTH_STAR.md`.
- [x] Add `CONTEXT.md`.
- [x] Add `CONTEXT-MAP.md`.
- [x] Add `AGENTS.md`.
- [x] Add ADR index.
- [x] Add glossary.
- [x] Add task backlog.
- [x] Add architecture and workflow docs.

**Verification gate:**
- [x] A new AI agent can read the docs and explain the project without old chat history.

## Phase 1 — Infrastructure & DB Skeleton
Goal: Setup FastAPI, PostgreSQL/PostGIS, and Next.js boilerplate via Docker Compose.
- [ ] Create `docker-compose.yml` for DB, Backend, Frontend.
- [ ] Setup FastAPI skeleton with SQLAlchemy.
- [ ] Setup Next.js skeleton.

**Verification gate:**
- [ ] `docker-compose up` runs successfully and endpoints return 200 OK.

## Phase 2 — Chat Webhook & AI Pipeline
Goal: Receive messages, process with Qwen LLM, and parse responses.
- [ ] Create webhook endpoints for WhatsApp/Telegram.
- [ ] Implement local LLM inference client (Qwen).
- [ ] Create prompt chains for extracting incident details.

**Verification gate:**
- [ ] Send a mock webhook payload and verify the LLM extracts the correct JSON representation of an incident.
