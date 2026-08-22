# Implement Next Task

Implement the next dependency-ready task from the active spec.

## Instructions

1. Read `docs/development-status.md` to identify the current phase.
2. Find the active spec directory in `.kiro/specs/` (the one with incomplete tasks).
3. Read the spec's `requirements.md`, `design.md`, and `tasks.md`.
4. Identify the next task that:
   - Is marked `- [ ]` (not yet done)
   - Has all prerequisite tasks already marked `- [x]`
   - Follows the dependency graph in the Task Dependency Graph section
5. Implement that single task following `design.md` exactly.
6. Write unit tests for the new behavior.
7. Run verification:
   ```bash
   pytest tests/
   python -m ruff check src/ tests/
   python -m mypy src/
   ```
8. If all pass, mark the task `- [x]` in `tasks.md`.
9. Report:
   - Task number and title
   - Files created/modified
   - Tests added
   - Verification results (test count, ruff, mypy)
   - Any deviations from requirements/design
   - Next available task(s)

## Constraints

- Implement ONLY ONE task per invocation.
- Do not implement tasks from future phases.
- Do not modify requirements.md or design.md.
- Do not introduce network, database, or cloud functionality.
- Do not require physical camera hardware in tests.
- Follow `.kiro/steering/coding-standards.md` for style.
- Follow `.kiro/steering/privacy.md` for data handling.
