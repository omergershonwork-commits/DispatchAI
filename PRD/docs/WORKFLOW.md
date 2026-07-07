# Incident Response Workflow

## Main Workflow Steps
1. **Initiation:** Victim sends a free-form text message via WhatsApp/Telegram.
2. **AI Processing:** Qwen LLM analyzes the text, asks clarifying questions if needed, and calms the victim.
3. **Categorization:** Incident is created in the DB with severity and location.
4. **Dispatch:** System finds the top 3 volunteers (weighted by distance, skills, physical stats) and messages them.
5. **Acceptance:** The first volunteer to reply "YES" is assigned. The others are notified it was taken.
6. **Resolution:** The volunteer completes the task and texts "DONE". System auto-closes the incident.

## Failure Handling
- **API Down:** Show massive red banner on frontend, send SMS/Email to SuperAdmins.
- **LLM Crash:** Queue requests and alert staff to dispatch manually.
- **Volunteer Rejection:** If a volunteer texts "NO", immediately contact the next best volunteer on the sorted list.
