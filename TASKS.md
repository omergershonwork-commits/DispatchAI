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

**Verification gate:**
- [ ] Send a mock Telegram webhook payload and verify the LLM extracts the correct JSON representation of an incident.
