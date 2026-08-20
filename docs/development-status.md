# ModDance Hero — Development Status

## Project Purpose

ModDance Hero (formerly OpenDance AI) is an open-source desktop application for dance practice, movement analysis, and rhythm-game-style scoring. It compares user movement captured via webcam against a reference dance video using pose detection, motion analysis, temporal alignment, and configurable scoring.

## Current Status

**Phase 3.5 complete. Multi-person subject tracking implemented and validated.**

| Phase | Status | Git Commit | Tests |
|-------|--------|------------|-------|
| Phase 0 — Project Foundation | ✅ Complete | `v0.1.0` | 38 |
| Phase 1 — Camera & Pose Pipeline | ✅ Complete | `v0.2.0-phase1` | +73 |
| Phase 2 — Pose Normalization & Motion | ✅ Complete | `v0.2.0` | +81 |
| Phase 3 — Scoring Pipeline | ✅ Complete | `v0.3.0` | +193 |
| Phase 3.5 — Subject Tracking & Diagnostics | ✅ Complete | `15b0fd5` | +40 |
| **Total** | | `15b0fd5` | **425** |

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

### Phase 3 — Scoring Pipeline (v0.3.0)

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

### Phase 3.5 — Multi-Person Subject Tracking (15b0fd5)

- **Configurable analysis FPS**: default changed to 15 FPS (near real-time on CPU)
- **PoseConfig.max_poses**: configurable 1–10 (default 1)
- **MultiPoseDetector**: detects up to 5 people simultaneously
- **SubjectTrack**: persistent identity with subject_id, confidence, state
- **Composite identity matching**: trajectory prediction + landmark geometry + body area
- **Ambiguity gate**: when two candidates score too similarly → UNCERTAIN (never switches)
- **Hard identity lock**: once selected, never auto-switches to another person
- **Manual correction API**: `select_subject()`, `correct_subject()`, `reset_tracking()`
- **TrackState**: UNLOCKED → TRACKING → OCCLUDED → LOST → UNCERTAIN
- **Diagnostic tools**: 7 standalone scripts for validation and benchmarking
- **Performance analysis**: documented in `.kiro/specs/scoring-pipeline/performance-analysis.md`

## Current Architecture

```
src/opendance/
├── app/          → Entry point, initialization
├── camera/       → CameraManager, FrameWorker, FPSMonitor, CameraState
├── pose/         → PoseDetector, MultiPoseDetector, SubjectTrack, PoseResult
├── motion/       → normalize_pose, angles, features, landmarks
├── video/        → ReferenceAnalyzer, ReferenceSequence, AnalysisCache
├── scoring/      → alignment, pose/angle/motion/timing compare, aggregation, rating, feedback, engine
├── alignment/    → (future)
├── analytics/    → (future)
├── storage/      → (future)
├── ui/           → CameraWidget, StatusIndicator, SkeletonRenderer
└── config/       → AppConfig, loader, defaults.toml

scripts/
├── camera_diagnostic.py          → Live webcam pose detection
├── video_analysis_diagnostic.py  → Full video analysis pipeline
├── landmark_replay.py            → Replay video with landmarks/angles/motion
├── detection_analysis.py         → Detection-drop segment analysis
├── multi_person_diagnostic.py    → Multi-person tracking diagnostic
├── subject_tracking_replay.py    → Visual subject identity validation
├── performance_diagnostic.py     → FPS benchmark tool
└── download_models.py            → MediaPipe model downloader
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
10. **Analysis FPS**: Default 15 FPS (0.93x real-time on CPU). Configurable 10/15/20/30.
11. **Subject tracking**: Persistent identity lock. Composite matching (trajectory + geometry + area). Ambiguity → OCCLUDED, never silent switch.
12. **Safety rule**: Identity correctness > detection continuity. Losing frames is preferable to scoring the wrong person.

## Quality Status

| Metric | Value |
|--------|-------|
| Total tests | 425 |
| All passing | ✅ |
| ruff | Clean |
| mypy | Clean (45 source files) |
| CI | GitHub Actions (Python 3.10/3.11, ubuntu-latest, libegl1+libgles2) |

## Known Limitations

- **Finger tracking**: 33-landmark Pose model does NOT track finger joints. Requires MediaPipe Hands (future).
- **Animated characters**: MediaPipe detects fewer candidates on MMD/3D-rendered content vs. real humans.
- **CPU inference**: ~60ms/frame. Default 15 FPS analysis keeps processing near real-time.
- **Body rotation**: Detection degrades when person faces away from camera (handled as OCCLUDED/LOST).
- **IMAGE_DIMENSIONS warning**: Known MediaPipe issue (#5639). Harmless — only affects Z-scale on non-square images, and scoring uses 2D (x,y) only.

## Next Step

Phase 4: Practice/Arcade mode UI, combo tracking, final grading.

## How to Resume Development

1. Clone and install: `pip install -e ".[dev]"`
2. Download model: `python scripts/download_models.py`
3. Run tests: `pytest tests/`
4. Read active spec: `.kiro/specs/scoring-pipeline/`
5. Run diagnostics: `python scripts/camera_diagnostic.py`
