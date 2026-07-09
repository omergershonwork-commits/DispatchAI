# Rules for AI Coding Agents

## Required reading before work
1. `CONTEXT.md`
2. `NORTH_STAR.md`
3. `CONTEXT-MAP.md`
4. `TASKS.md`
5. Relevant ADRs in `docs/adr/ADR_INDEX.md`

## Working loop
For every task:
1. Restate the task in one sentence.
2. Identify the phase/task ID.
3. Inspect existing files before proposing edits.
4. Make the smallest useful change.
5. Run the relevant verification command.
6. Update task status if done.
7. Update docs when behavior changes.
8. Add/update ADRs when architecture changes.

## Do not
- Do not build unrelated features.
- Do not introduce new frameworks without approval (e.g., sticking to FastAPI + Next.js).
- Do not perform broad refactors unless assigned.
- Do not change public contracts without approval.
- Do not mark work complete without verification (Comprehensive Unit/Integration tests are required for MVP).

## Definition of done
- Code compiles and runs via Docker.
- Pytest unit and integration tests pass.
- Acceptance criteria are satisfied.
- Docs are updated.
- Risks are listed.
