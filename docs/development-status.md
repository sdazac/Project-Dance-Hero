# ModDance Hero — Development Status

## Project Purpose

ModDance Hero (formerly OpenDance AI) is an open-source desktop application for dance practice, movement analysis, and rhythm-game-style scoring. It compares user movement captured via webcam against a reference dance video using pose detection, motion analysis, temporal alignment, and configurable scoring.

## Current Status

**Phase 4 in progress. Core practice mode loop, AV playback, and UI overlays implemented.**

| Phase | Status | Git Commit | Tests |
|-------|--------|------------|-------|
| Phase 0 — Project Foundation | ✅ Complete | `v0.1.0` | 38 |
| Phase 1 — Camera & Pose Pipeline | ✅ Complete | `v0.2.0-phase1` | +73 |
| Phase 2 — Pose Normalization & Motion | ✅ Complete | `v0.2.0` | +81 |
| Phase 3 — Scoring Pipeline | ✅ Complete | `v0.3.0` | +193 |
| Phase 3.5 — Subject Tracking & Diagnostics | ✅ Complete | `15b0fd5` | +40 |
| **Phase 4 — Practice Mode UI & Arcade Scoring** | 🟡 **In Progress**| `local` | (see total) |
| **Total** | | `local` | **625** |

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

### Phase 4 — Practice Mode UI & Arcade Scoring (In Progress)

- **SessionTracker**: Arcade-style scoring logic tracking combos, dynamic multipliers, and real-time accuracy mapping to SS-F grades.
- **SilhouetteRenderer**: Replaced wireframe with a transparent, organic humanoid avatar (RGBA canvas, rounded joints, mirror mode).
- **AV Playback Integration**: Replaced OpenCV playback with `QMediaPlayer` and `QVideoSink` for fluid, hardware-accelerated video/audio with no UI blocking.
- **Asynchronous Processing**: `ReferenceAnalyzer` offloaded to a background `QThread` (AnalysisWorker) with a loading overlay to prevent UI freezes.
- **PracticeWindow**: Master window orchestrating video playback, camera background processing, floating UI overlays (HUD & Silhouette), and the gameplay loop.

#### Phase 4 sub-specs (this iteration)

Practice Mode was hardened through a series of focused, spec-driven iterations
(each with requirements → design → tasks and unit/property/integration tests):

- **`practice-mode-mvp`** ✅ — Decoupled the single 33 ms game loop into
  independent render and scoring timers (`PracticeConfig` render/scoring FPS),
  real monotonic timestamps in `FrameWorker`, restored combo/grade semantics,
  latest-wins pose handling, effective-FPS diagnostics, and timer/resource
  cleanup on pause/finish/error/close.
- **`scoring-accuracy-fix`** ✅ — Fixed a correctness bug where
  `accuracy_percentage` could exceed 100% during combo streaks (the arcade
  multiplier leaked into the accuracy ratio). Accuracy is now the
  multiplier-independent mean of per-rating quality weights
  (`RATING_QUALITY`: PERFECT 1.0 / GREAT 0.75 / OK 0.50 / MEH 0.30 / MISS 0.0),
  bounded to [0, 100] and order-independent. Covered by Hypothesis property
  tests (bounded, order-independent, endpoints, mean).
- **`live-full-scoring`** ✅ — The live scoring path now feeds real player joint
  angles (`compute_joint_angles`) and motion features (`motion_for_latest` over a
  bounded rolling pose buffer) into `score_frame`, so all four similarity metrics
  (pose/angle/motion/timing) contribute during practice.
- **`practice-playback-controls`** ✅ — Seek slider + configurable playback-speed
  control wired to `QMediaPlayer`, preserving position-based scoring alignment.
  A seek clears the live pose buffer (temporal discontinuity); the selected speed
  is preserved across restart. Config (`PracticeConfig.playback_speeds` /
  `default_playback_speed`) with loader validation, plus pure slider↔ms helpers,
  all unit-tested (offscreen widget tests included).
- **`practice-io-controls`** 🟡 In progress — Camera management (restart + input
  device/port change via `CameraManager.restart` / `device_index`) and a
  reference-video analysis progress bar. The analyzer now accepts an additive
  `progress_callback`; `AnalysisWorker` exposes a `progress(int)` signal; a pure
  `progress_percent(done, total)` helper maps sample counts to a bounded percent.
  Backend + helpers + tests are done (analyzer progress, camera restart,
  percent helper). Remaining: the `PracticeWindow` UI wiring — QProgressBar,
  device selector (QSpinBox), "Restart Camera" button, and camera status label
  (spec tasks 5–6).

## Current Architecture

```text
src/opendance/
├── app/          → Entry point, initialization
├── camera/       → CameraManager, FrameWorker, FPSMonitor, CameraState
├── pose/         → PoseDetector, MultiPoseDetector, SubjectTrack, PoseResult
├── motion/       → normalize_pose, angles, features, landmarks
├── video/        → ReferenceAnalyzer, ReferenceSequence, AnalysisCache
├── scoring/      → alignment, pose/angle/motion/timing compare, aggregation, rating, feedback, engine, session_tracker
├── alignment/    → (future)
├── analytics/    → (future)
├── storage/      → (future)
├── ui/           → CameraWidget, StatusIndicator, SkeletonRenderer, practice_window, scoreboard_widget, silhouette_renderer
└── config/       → AppConfig, loader, defaults.toml

scripts/
├── camera_diagnostic.py          → Live webcam pose detection
├── video_analysis_diagnostic.py  → Full video analysis pipeline
├── landmark_replay.py            → Replay video with landmarks/angles/motion
├── detection_analysis.py         → Detection-drop segment analysis
├── multi_person_diagnostic.py    → Multi-person tracking diagnostic
├── subject_tracking_replay.py    → Visual subject identity validation
├── performance_diagnostic.py     → FPS benchmark tool
├── download_models.py            → MediaPipe model downloader
└── run_practice_mode.py          → Phase 4 Practice Mode entry point

````

## Important Architectural Decisions

1. **Threading**: Single FrameWorker QThread for camera + pose. UI receives finished results via signals.



2. **MediaPipe**: VIDEO running mode, init once, reuse. Import path: `mediapipe.tasks.python.vision`.



3. **Normalization**: World landmarks preferred for center/scale. Image-space fallback. leave\_none for missing data.



4. **Joint angles**: Signed 2D atan2(cross, dot) → [-180, 180]. NOT arccos.



5. **Motion**: Central differences (interior), forward/backward at boundaries. timestamp\_ms is authoritative time.



6. **Cache**: gzip JSON metadata + numpy.savez\_compressed arrays. No pickle. Disabled by default.



7. **Configuration**: Frozen dataclasses, TOML defaults with merge/validation, opt-in features.



8. **Privacy**: All processing local. No network. No frame logging.



9. **Scoring weights**: pose=0.40, angle=0.25, motion=0.20, timing=0.15 (configurable).



10. **Analysis FPS**: Default 15 FPS (0.93x real-time on CPU). Configurable 10/15/20/30.



11. **Subject tracking**: Persistent identity lock. Composite matching (trajectory + geometry + area). Ambiguity → OCCLUDED, never silent switch.



12. **Safety rule**: Identity correctness > detection continuity. Losing frames is preferable to scoring the wrong person.



13. **AV Playback & UI Overlays**: `PySide6.QtMultimedia` handles native audio/video. OpenCV is strictly reserved for frame analytics and generating the RGBA silhouette. HUD and Silhouette are implemented as translucent `QLabel` widgets floating safely over the native `QVideoSink`.



14. **Data Immutability Compliance**: `dataclasses.replace` is used to safely update `timestamp_ms` on the frozen `NormalizedPose` during the gameplay loop, preventing `FrozenInstanceError` while maintaining pipeline integrity.




## Quality Status

| **Metric**  | **Value**                                                          |
| ----------- | ------------------------------------------------------------------ |
| Total tests | 625                                                                |
| All passing | ✅                                                                  |
| ruff        | Clean                                                              |
| mypy        | Clean (51 source files)                                            |
| CI          | GitHub Actions (Python 3.10/3.11, ubuntu-latest, libegl1+libgles2) |

## Known Limitations

- **Finger tracking**: 33-landmark Pose model does NOT track finger joints. Requires MediaPipe Hands (future).



- **Animated characters**: MediaPipe detects fewer candidates on MMD/3D-rendered content vs. real humans.



- **CPU inference**: \~60ms/frame. Default 15 FPS analysis keeps processing near real-time.



- **Body rotation**: Detection degrades when person faces away from camera (handled as OCCLUDED/LOST).



- **IMAGE\_DIMENSIONS warning**: Known MediaPipe issue (#5639). Harmless — only affects Z-scale on non-square images, and scoring uses 2D (x,y) only.



- **Silhouette Z-Index**: The 2D filled silhouette does not currently respect Z-depth (e.g., arms crossing the torso appear flat).



- **Phase 4 Scoring Inputs**: ✅ Resolved. The live scoring path (`_scoring_tick`, formerly `_game_loop_tick`) now feeds real player joint angles (`compute_joint_angles`) and motion features (`motion_for_latest` over a bounded rolling pose buffer) into `score_frame`, so all four similarity metrics (pose/angle/motion/timing) contribute during practice.




## Next Step

Phase 4 MVP hardening is underway via focused sub-specs. Completed this iteration:
`practice-mode-mvp`, `scoring-accuracy-fix`, and `live-full-scoring` (all live
scoring metrics now contribute; accuracy is correct and bounded).

Immediate next step: finish **`practice-io-controls`** — wire the analysis
progress bar (QProgressBar), the camera device selector (QSpinBox), the "Restart
Camera" button, and the camera status label into `PracticeWindow` (spec tasks
5–6), then run the checkpoint. The camera/analyzer backend, the `progress_percent`
helper, and their tests are already done.

Remaining toward a full MVP (planned order):
1. Finish I/O controls UI (camera restart/device + analysis progress bar) —
   in progress.
2. Session analytics: accuracy-over-time and weak-section detection
   (`analytics/` layer is currently empty).
3. Arcade Mode: full-song play-through, combo/score, final grade.

## How to Resume Development

1. Clone and install: `pip install -e ".[dev]"`



2. Download model: `python scripts/download_models.py`



3. Run tests: `pytest tests/`



4. Read active spec: `.kiro/specs/scoring-pipeline/`



5. Run diagnostics: `python scripts/camera_diagnostic.py`



6. Test Practice Mode: `python scripts/run_practice_mode.py`

```