# ADR Index

## ADR-001 — Use Local Qwen LLM
Status: Accepted
Use a local open-source LLM (Qwen) on AMD GPUs to ensure data privacy and multilingual support.

## ADR-002 — FastAPI Monolith
Status: Accepted
Use a Python FastAPI monolith rather than microservices to simplify MVP deployment while supporting async AI processing.

## ADR-003 — OpenStreetMap Self-hosted
Status: Accepted
Use OSM for map tiles to maintain full control and privacy over location data.

## ADR-004 — Chat Onboarding
Status: Accepted
Volunteers onboard entirely via chat instead of a web form to reduce friction.

## ADR-005 — Chain of Smaller Prompts
Status: Accepted
Use a chain of smaller, focused prompts for AI inference rather than one giant prompt. This significantly increases reliability, debugging capabilities, and testability.

## ADR-006 — Async Webhook Processing
Status: Accepted
Immediately return `200 OK` upon receiving webhooks from WhatsApp/Telegram, and process the LLM inference asynchronously using FastAPI `BackgroundTasks` with a concurrency lock (Semaphore). This prevents webhook timeouts, duplicate message retries, and GPU VRAM exhaustion.
