# Project Context

## Current Phase
Phase 0: Project context, repository setup, and architecture definition.

## Current Project Status
Initial design completed via AI grilling session. Ready for scaffolding.

## User/Business Intent
To reduce the burden on emergency dispatch staff by automating volunteer matching and communication using a local LLM.

## Binding Decisions
- **Backend:** Python FastAPI (Monolith).
- **Frontend:** React (Next.js) + Mapbox GL JS / Leaflet (rendering OSM tiles).
- **Database:** PostgreSQL + PostGIS.
- **AI Model:** Qwen (local on AMD GPUs).
- **Mapping:** OpenStreetMap (self-hosted).
- **Chat:** Webhooks via Official APIs (Meta/Telegram).
- **Prompt Architecture:** A chain of smaller, focused prompts (e.g., extract severity -> query DB -> score volunteers -> draft response) for higher reliability.

## Latest Implementation Decisions
- Onboarding is done entirely via the chatbot.
- Staff UI uses OAuth, requiring SuperAdmin approval.
- Map updates via Frequent Polling (30-60s).

## Current Blockers
- None. Initializing repository.

## Current Priorities
- Scaffolding the FastAPI backend and Next.js frontend.
- Implementing the webhook receiver for WhatsApp/Telegram.

## Current MVP Definition
Handles ~100 volunteers and ~10 incidents/day in English. Autonomous dispatch without staff approval, relying on a local Qwen LLM.

## Important Assumptions
- WhatsApp/Telegram business APIs can be approved quickly.
- AMD GPU instances have enough VRAM for the selected Qwen model quantization.

## Preferred Development Workflow
Manual deployment via SSH using `docker-compose up`. 
