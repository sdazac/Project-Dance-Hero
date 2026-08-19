# OpenDance AI — Development Status

## Project Purpose

OpenDance AI is an open-source desktop application for dance practice, movement analysis, and rhythm-game-style scoring. It compares user movement captured via webcam against a reference dance video using pose detection, motion analysis, temporal alignment, and configurable scoring.

## Current Status

**Phase 3 complete. All scoring pipeline modules implemented and tested.**

| Phase | Status | Git Tag | Tests |
|-------|--------|---------|-------|
| Phase 0 — Project Foundation | ✅ Complete | `v0.1.0` | 38 |
| Phase 1 — Camera & Pose Pipeline | ✅ Complete | `v0.2.0-phase1` | +73 |
| Phase 2 — Pose Normalization & Motion | ✅ Complete | `v0.2.0` | +81 |
| Phase 3 — Scoring Pipeline | ✅ Complete | — | +193 |
| **Total** | | `v0.2.0` (da0386a) | **385** |

## Completed Phases

### Phase 0 — Project Foundation (v0.1.0)

- Python package (pyproject.toml, src layout)
- TOML configuration system (defaults + user overrides + validation)
- Structured logging (ISO 8601, env-driven level)
- PySide6 entry point
- pytest + hypothesis infrastructure
- GitHub Actions CI (ruff, mypy, pytest on Python 3.10/3.11)
- README, LICENSE (MIT), .gitignore

### Phase 1 — Camera & Pose Pipeline (v0.2.0-phase1)

- Camera lifecycle (CameraManager, CameraState, FrameWorker QThread)
- MediaPipe Pose Landmarker integration (init once, reuse)
- FPS measurement (rolling window)
- Skeleton overlay rendering (visibility threshold)
- PySide6 CameraWidget with Start/Stop, StatusIndicator
- Configuration extensions ([camera], [pose])
- Resource cleanup on stop/exit

### Phase 2 — Pose Normalization & Motion (v0.2.0)

- Landmark index constants (33 MediaPipe landmarks)
- Pose normalization (world-preferred, image fallback, body center/scale)
- Signed joint angles (atan2, [-180, 180])
- Motion features (central differences, velocity/acceleration/direction)
- Reference video analysis (deterministic FPS sampling)
- Analysis cache (gzip JSON + numpy.savez_compressed, no pickle)
- Configuration extensions ([normalization], [motion], [reference])

### Phase 3 — Scoring Pipeline

- ComparisonConfig dataclass with 8 configurable parameters
- LANDMARK_REGIONS mapping (33 landmarks → 6 body regions)
- Temporal alignment (nearest-frame, no DTW, no interpolation)
- Pose comparison (2D x/y Euclidean, z excluded, scale factor)
- Angle comparison (circular wraparound, min(abs_diff, 360-abs_diff))
- Motion comparison (speed similarity + direction dot product, acceleration excluded)
- Timing comparison (phase-alignment: moving/still state match)
- Score aggregation (weighted combination, None renormalization)
- Event rating (PERFECT/GREAT/OK/MEH/MISS from thresholds)
- Structured feedback (angle severity=error/90, pose severity=dist/0.5)
- ScoringEngine orchestrator (score_frame, score_sequence)
- Configuration extensions ([scoring.comparison])

## Current Architecture

```
src/opendance/
├── app/          → Entry point, initialization
├── camera/       → CameraManager, FrameWorker, FPSMonitor, CameraState
├── pose/         → PoseDetector (MediaPipe), PoseResult, Landmark
├── motion/       → normalize_pose, angles, features, landmarks
├── video/        → ReferenceAnalyzer, ReferenceSequence, AnalysisCache
├── scoring/      → alignment, pose/angle/motion/timing compare, aggregation, rating, feedback, engine
├── alignment/    → (future)
├── analytics/    → (future)
├── storage/      → (future)
├── ui/           → CameraWidget, StatusIndicator, SkeletonRenderer
└── config/       → AppConfig, loader, defaults.toml
```

## Important Architectural Decisions

1. **Threading**: Single FrameWorker QThread for camera + pose. UI receives finished results via signals.
2. **MediaPipe**: VIDEO running mode, init once, reuse. Import path: `mediapipe.tasks.python.vision`.
3. **Normalization**: World landmarks preferred for center/scale. Image-space fallback. leave_none for missing data.
4. **Joint angles**: Signed 2D atan2(cross, dot) → [-180, 180]. NOT arccos.
5. **Motion**: Central differences (interior), forward/backward at boundaries. timestamp_ms is authoritative time.
6. **Cache**: gzip JSON metadata + numpy.savez_compressed arrays. No pickle. Disabled by default.
7. **Configuration**: Frozen dataclasses, TOML defaults with merge/validation, opt-in features.
8. **Privacy**: All processing local. No network. No frame logging.
9. **Scoring weights**: pose=0.40, angle=0.25, motion=0.20, timing=0.15 (configurable).

## Quality Status

| Metric | Value |
|--------|-------|
| Total tests | 385 |
| All passing | ✅ |
| Coverage | ~92% |
| ruff | Clean |
| mypy | Clean (44 source files) |
| CI | GitHub Actions (Python 3.10/3.11, ubuntu-latest, libegl1+libgles2) |

## Phase 3 — Scoring Pipeline (COMPLETE)

**Status: Implementation complete. All tests passing.**

### Implemented Modules

1. **Temporal alignment** — nearest-frame timestamp-ratio mapping (no DTW)
2. **Pose comparison** — per-landmark 2D Euclidean distance → [0, 100] score
3. **Angle comparison** — circular difference with wraparound → [0, 100]
4. **Motion comparison** — speed + direction similarity → [0, 100]
5. **Timing comparison** — phase-alignment (moving/still state match) → [0, 100]
6. **Aggregation** — weighted combination using existing ScoringWeights, None renormalization
7. **Event rating** — PERFECT/GREAT/OK/MEH/MISS from existing thresholds
8. **Feedback** — structured FeedbackItems (body region, issue type, severity)
9. **ScoringEngine** — orchestrator (score_frame, score_sequence)

### Architectural Properties

- All scoring modules are pure, stateless, deterministic functions
- No DTW, no interpolation, no peak detection
- Direction similarity clamped [0,1] (opposite = 0)
- Timing is phase-alignment, not speed comparison
- Acceleration excluded from motion scoring
- Feedback: angle severity=error/90, pose severity=dist/0.5, capped [0,1]
- LANDMARK_REGIONS maps all 33 indices to 6 body regions

### Explicit Out of Scope (Phase 3)

- Practice/Arcade mode UI
- Combo tracking, final grading
- DTW or advanced warping
- ML-based scoring
- Music/beat synchronization
- Cloud/network/database
- UI rendering of scores

### Spec Location

`.kiro/specs/scoring-pipeline/` (requirements.md, design.md, tasks.md)

## Known Future Work

- Phase 4: Practice/Arcade mode UI, combo, final grading
- DTW temporal alignment (optional enhancement)
- Beat detection / music sync
- ML scoring models
- Historical tracking
- Mobile support

## Next Step

Implement Phase 4 (Practice/Arcade mode UI, combo tracking, final grading) or commit Phase 3 and tag.

## How to Resume Development

1. Clone and install: `pip install -e ".[dev]"`
2. Download model: `python scripts/download_models.py`
3. Run tests: `pytest tests/`
4. Read active spec: `.kiro/specs/scoring-pipeline/`
5. Follow the task dependency graph
