# AI Agent Development Workflow

## Working Loop
1. Read context files.
2. Pick exactly one task from `TASKS.md`.
3. Inspect relevant files before editing.
4. Produce a short implementation plan.
5. Implement the smallest complete slice.
6. Run verification (pytest / docker compose up).
7. Update docs/tasks.
8. Commit with a clear message.
9. Start a new session for the next phase.

## Agent Roles
- **Architect agent:** Architecture changes, ADRs.
- **Builder agent:** Implementation, APIs, UI.
- **Reviewer agent:** Correctness, edge cases, security.
- **Debugger agent:** Failures, logs, root cause analysis.

## Prompt Rules
Every coding prompt should include:
- Task ID
- Exact files allowed to change
- Acceptance criteria
- Verification command
- Instruction to update docs/tasks
