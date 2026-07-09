# System Architecture

## System Overview
A modular monolith backend (FastAPI) handling chat webhooks, AI inference (Qwen), and frontend API requests. The frontend is a Next.js React application displaying a real-time OpenStreetMap dashboard.

## Component Diagram
[WhatsApp/Telegram] <--(Webhooks)--> [FastAPI Backend] <--(SQL)--> [PostgreSQL + PostGIS]
                                           |
                                       [Qwen LLM]
                                           |
[Staff Browser] <-----(Long Polling)-------/

## Component Responsibilities
- **Chat Webhook Module:** Receives raw messages, handles API formatting.
- **AI Inference Module:** Communicates with the local Qwen LLM. Uses a **chain of smaller prompts** (1. Categorize/Extract Severity, 2. Extract Location, 3. Formulate response to victim) for high reliability and testability instead of a single giant prompt.
- **Dispatch Engine:** Calculates distances using PostGIS and applies hardcoded weights to volunteer stats.
- **Next.js Frontend:** Renders the OSM map, clusters incident pins, displays side panels, and handles OAuth.

## Data Flow
1. Victim texts Bot -> Webhook triggers FastAPI.
2. FastAPI sends text to Qwen LLM -> extracts incident details.
3. FastAPI saves incident to PostgreSQL.
4. Dispatch Engine queries PostGIS for nearest available volunteers.
5. FastAPI sends WhatsApp messages to top 3 volunteers.
6. First volunteer to reply "YES" is assigned; others are cancelled.
7. Frontend polls FastAPI every 30s and updates the map.

## Storage Layout
- PostgreSQL with PostGIS extension for spatial queries.
- Tables: `volunteers`, `incidents`, `staff`, `messages`.

## Security Model
- OAuth (Google/MS) for Staff UI, gated by SuperAdmin approval.
- Webhook signature verification for Chat APIs.
- Retain only incident metadata; delete personal contact info post-incident.
