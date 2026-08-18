# AI Agent Instructions — OpenDance AI

This file provides instructions for AI coding agents (GitHub Copilot, Kiro, Claude, etc.) working on this repository.

## Before You Start

1. Read `docs/development-status.md` for current project state.
2. Read the active spec in `.kiro/specs/<feature-name>/` (requirements.md → design.md → tasks.md).
3. Read the relevant `.kiro/steering/` files for project-wide constraints.
4. Check `tasks.md` for the next incomplete task that has all dependencies satisfied.

## Spec-Driven Development Workflow

This project follows a strict **requirements → design → tasks → implementation** workflow:

```
.kiro/specs/<feature>/requirements.md  ← What to build (acceptance criteria)
.kiro/specs/<feature>/design.md        ← How to build it (architecture, interfaces)
.kiro/specs/<feature>/tasks.md         ← Implementation order (dependency graph)
```

**Rules:**
- Implement tasks in dependency order only.
- Do not skip ahead or implement tasks whose dependencies are incomplete.
- Do not modify requirements.md or design.md without explicit user approval.
- Mark tasks `[x]` only after passing pytest + ruff + mypy.

## Architecture Layers

| Layer | Directory | Responsibility |
|-------|-----------|----------------|
| App | `src/opendance/app/` | Entry point, initialization order |
| UI | `src/opendance/ui/` | PySide6 widgets, display, user interaction |
| Camera | `src/opendance/camera/` | Camera lifecycle, frame acquisition, FPS |
| Pose | `src/opendance/pose/` | MediaPipe detection, landmarks, results |
| Motion | `src/opendance/motion/` | Feature extraction (velocity, angles) |
| Alignment | `src/opendance/alignment/` | Temporal synchronization |
| Scoring | `src/opendance/scoring/` | Accuracy, ratings, grades |
| Analytics | `src/opendance/analytics/` | Timeline metrics, weak sections |
| Video | `src/opendance/video/` | Reference video loading, playback |
| Storage | `src/opendance/storage/` | Cache, settings persistence |
| Config | `src/opendance/config/` | TOML configuration, dataclass models |

**Restrictions:**
- Do not put pose/scoring/motion logic inside UI widgets.
- Do not create global mutable state.
- Do not block the UI thread with camera I/O or ML inference.
- Keep layers independent — each module should be testable in isolation.

## Verification Checklist

After every task:

- [ ] `pytest tests/` — all tests pass
- [ ] `python -m ruff check src/ tests/` — no lint errors
- [ ] `python -m mypy src/` — no type errors
- [ ] New code has unit tests
- [ ] No hardware required for tests (mock camera/MediaPipe)
- [ ] `QT_QPA_PLATFORM=offscreen` for Qt widget tests
- [ ] Task marked `[x]` in tasks.md

## What NOT to Do

- Do not implement features from future phases.
- Do not add network/cloud/database functionality.
- Do not commit MediaPipe `.task` model binaries (use `scripts/download_models.py`).
- Do not log camera frames or personal data.
- Do not hardcode configurable values.
- Do not introduce dependencies not declared in pyproject.toml.
- Do not weaken or delete existing tests.

## Reporting Format

After completing a task, report:

1. **Files changed** (created/modified)
2. **Tests added** (count and coverage areas)
3. **Verification results** (pytest count, ruff, mypy)
4. **Deviations** from requirements/design (if any)
5. **Remaining tasks** in the current spec
