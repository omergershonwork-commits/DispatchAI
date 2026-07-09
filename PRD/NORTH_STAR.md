# AI-Rescue Connect: North Star

## Product One-Liner
An AI-driven volunteer management system that autonomously dispatches the most suitable emergency response volunteers via chat apps (WhatsApp/Telegram).

## Problem Statement
Emergency response staff are overwhelmed by coordinating and dispatching volunteers manually when incidents occur. 

## Target User
- **People in Need**: Requesting help via WhatsApp/Telegram in emergencies.
- **Volunteers**: Receiving tasks and onboarding via WhatsApp/Telegram.
- **Emergency Staff**: Monitoring the map dashboard and managing edge cases.

## Main Use Case
A person in need texts the bot; the local AI (Qwen) categorizes the incident, determines the required volunteer parameters, and instantly dispatches the top 3 closest/best-suited available volunteers.

## MVP Goal
- English-only text interaction (via Qwen LLM).
- Fully autonomous dispatch (contacts top 3, first "YES" wins).
- React/Next.js map dashboard for staff to monitor and intervene.
- Small scale (~100 volunteers, ~10 incidents/day).

## Non-Goals
- Dedicated mobile app for volunteers (chat apps permanently).
- Database backups and advanced spam prevention.
- High-frequency live location tracking (using static home address/temp pins).

## Success Definition
The system autonomously handles an incident from initiation to resolution (volunteer replies "DONE") with zero manual staff intervention, while keeping the victim calm via natural AI chat.

## Reliability/Quality Principles
- Local-first AI for data privacy.
- High-visibility failures: Alert staff loudly on API or LLM crashes.

## Constraints
- Must run locally on AMD cloud instances with GPUs.
- OpenStreetMap (OSM) for all mapping to maintain data sovereignty.
