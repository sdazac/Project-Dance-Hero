# GitHub Copilot Instructions — OpenDance AI

## Project Overview

OpenDance AI is an open-source desktop application for dance practice, movement analysis, and rhythm-game-style scoring. It compares user movement captured via webcam against a reference dance video using pose detection, motion analysis, and configurable scoring.

**Technology stack:** Python 3.10+, PySide6, OpenCV, MediaPipe Pose Landmarker, NumPy, SciPy.

## Source of Truth

Before making any implementation changes, read the relevant documentation:

1. **Steering files** (project-wide rules): `.kiro/steering/`
   - `product.md` — Product definition, MVP goals, game modes
   - `architecture.md` — Layers, tech stack, data flow, restrictions
   - `coding-standards.md` — Python conventions, naming, functions, testing
   - `ai-ml.md` — Pose estimation, similarity, temporal alignment, ML rules
   - `privacy.md` — Local-first, no network transmission, no frame logging
   - `testing.md` — Test strategy, boundary tests, regression rules

2. **Active spec** (current feature being implemented): `.kiro/specs/<feature-name>/`
   - `requirements.md` — Acceptance criteria (source of truth for behavior)
   - `design.md` — Architecture, components, interfaces, data flow
   - `tasks.md` — Ordered implementation tasks with dependencies

3. **Development status**: `docs/development-status.md`

## Workflow

Follow this strict workflow for all implementation:

1. **Identify the active spec** — Check which `.kiro/specs/` directory has incomplete tasks in its `tasks.md`.
2. **Read the spec** — Read `requirements.md`, `design.md`, and `tasks.md` for context.
3. **Implement only dependency-ready tasks** — A task is ready only when all tasks it depends on are marked `[x]`.
4. **Write tests alongside implementation** — Every new module needs unit tests.
5. **Verify before marking complete** — Run `pytest`, `ruff check`, and `mypy` after each task.
6. **Mark tasks done** — Change `- [ ]` to `- [x]` in `tasks.md` only after verification passes.
7. **Report results** — List files changed, tests added, verification results, deviations, and remaining tasks.

## Critical Rules

- **Do NOT implement tasks from future phases** unless explicitly requested.
- **Do NOT introduce network functionality**, databases, cloud APIs, or remote services.
- **Do NOT add scoring, temporal alignment, DTW, or game modes** unless the active spec requires them.
- **Do NOT log raw camera frames** or personal user data at any log level.
- **Do NOT hardcode** scoring thresholds, camera resolution, FPS, or playback speeds — use the configuration system.
- **Do NOT put business logic in UI widgets** — keep layers separate per architecture.md.
- **Do NOT modify completed specs** (requirements.md/design.md) without explicit user approval.
- **All processing is local** — never transmit frame data externally.

## Verification Requirements

After every implementation task:

```bash
# Run all tests
pytest tests/

# Run linting
python -m ruff check src/ tests/

# Run type checking
python -m mypy src/
```

All three must pass before marking a task complete.

## Configuration System

All configurable values go through the TOML-based configuration system:
- Defaults: `src/opendance/config/defaults.toml`
- Models: `src/opendance/config/models.py` (frozen dataclasses)
- Loader: `src/opendance/config/loader.py` (validation + merge)

New configuration sections follow the same pattern: add TOML section, add frozen dataclass, extend `_build_config()` with validation.

## Testing Strategy

- Use `pytest` with `hypothesis` for property-based tests where applicable.
- All tests must work without physical camera hardware or GPU (`QT_QPA_PLATFORM=offscreen`).
- Mock `cv2.VideoCapture` and MediaPipe in unit tests.
- Test boundary conditions explicitly.
- Never commit tests that require network access or real hardware.
