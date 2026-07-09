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
- [x] BE-001: Create FastAPI backend skeleton with `/health`, `/ready`, tests, and Docker support.
- [x] BE-002: Add PostgreSQL/PostGIS service, SQLAlchemy DB skeleton, and DB-backed readiness check.
- [ ] Setup Next.js skeleton.

**Verification gate:**
- [ ] `docker compose up` runs successfully and endpoints return 200 OK.

## Phase 2 — Chat Webhook & AI Pipeline
Goal: Receive Telegram messages, process with Qwen LLM, and parse responses.
- [x] BE-003: Create Telegram webhook ingestion skeleton.
- [x] BE-004: Implement local Qwen inference client skeleton.
- [x] BE-005: Create prompt chains for extracting incident details.
- [x] BE-006: Add extraction decision and follow-up support.
- [x] BE-007: Wire Telegram webhook to incident extraction.
- [x] BE-008: Add automatic Qwen request headers for local and remote inference.
- [x] BE-009a: Send Telegram bot replies after webhook extraction.
- [x] BE-009b: Persist Telegram incidents and pending conversation state.

**Verification gate:**
- [ ] Send a real Telegram bot message and verify the backend replies in Telegram and persists the incident.
