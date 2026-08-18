# Checkpoint Verification

Run a full project verification checkpoint without implementing new features.

## Instructions

1. Run all verification commands:
   ```bash
   pytest tests/
   pytest tests/ --cov=opendance --cov-report=term-missing
   python -m ruff check src/ tests/
   python -m mypy src/
   ```

2. Inspect for:
   - Failing tests
   - Lint warnings or errors
   - Type errors
   - Orphaned imports or missing exports
   - Files that should not be committed (model binaries, secrets, .env)
   - Broken `__init__.py` exports

3. Check `git status` for:
   - Uncommitted changes
   - Untracked files that need attention
   - Model binaries accidentally staged

4. Report:
   - Total test count and pass/fail
   - Coverage percentage
   - ruff result
   - mypy result
   - Any issues found
   - Current git state
   - Active spec progress (tasks completed vs remaining)

## Constraints

- Do NOT implement new features.
- Do NOT modify application behavior.
- Fix ONLY real issues (broken imports, lint errors in existing code).
- If a test fails, report it — do not silently delete or weaken the test.
