# Requirements: Practice Mode MVP & Real-Time Performance

## Introduction

The project now has a functional Practice Mode UI: it loads a reference video, plays it with audio, captures the webcam, detects the user's pose, and computes a live score. However, the live body tracking feels slow and choppy (low effective frame rate), which undermines the practice experience.

This spec closes the MVP by making the real-time practice loop smooth and responsive, while ensuring the complete Practice Mode flow works end-to-end. The focus is on perceived fluidity of the pose overlay and scoring, correct temporal behavior, and a stable, usable MVP — without introducing new architecture or ML models.

This spec builds on completed work: camera/pose pipeline (Phase 1), normalization/motion (Phase 2), scoring engine (Phase 3), subject tracking (Phase 3.5), and the initial Practice Mode UI (Phase 4 UI).

## Glossary

- **Capture FPS**: rate at which frames are read from the webcam.
- **Inference FPS**: rate at which pose detection completes (bounded by CPU, ~16 FPS).
- **Render FPS**: rate at which the UI updates the on-screen silhouette/overlay.
- **Scoring FPS**: rate at which frames are compared against the reference and scored.
- **Practice loop**: the repeating cycle of capture → detect → normalize → score → render.
- **Silhouette**: the translucent humanoid figure rendered from the user's live pose.
- **Reference sequence**: the precomputed per-frame analysis of the loaded dance video.

## Decoupled Rates Principle

The system uses three independent rates so smoothness and correctness do not
compete for the same budget:

- **Render (high, fluid)**: updates the silhouette as often as possible from the
  latest available pose (target ≥ 25 FPS visually), so movement looks smooth.
- **Inference (medium, CPU-bound)**: pose detection runs as fast as the CPU
  allows (~15–16 FPS) on a worker thread; the newest result always wins.
- **Scoring (low, deliberate)**: comparison against the reference runs at a lower
  configurable rate (e.g. 10–15 FPS) to avoid overloading the CPU, since
  scoring 20+ times per second is unnecessary for meaningful feedback.

Displaying fluid silhouette movement is decoupled from how often we compute a score.

## Requirements

### Requirement 1 — Smooth live pose tracking

**User Story:** As a user practicing a dance, I want my on-screen body silhouette to move smoothly and keep up with my real movement, so that I can trust the visual feedback.

#### Acceptance Criteria

1. WHEN the webcam is active THEN the system SHALL render the user silhouette at a perceived rate of at least 25 updates per second on typical hardware.
2. WHEN pose inference cannot keep pace with capture THEN the system SHALL drop stale frames rather than queue them, so the displayed pose reflects the most recent movement.
3. WHEN a new pose result is available THEN the system SHALL update the silhouette using the latest result without waiting for scoring to complete.
4. WHEN the practice loop runs THEN the system SHALL NOT block the UI thread with pose inference or heavy image processing.
5. WHEN measuring live performance THEN the system SHALL expose the current effective render FPS, inference FPS, and scoring FPS for diagnostics.
6. WHEN the silhouette is updated THEN its refresh rate SHALL be independent of the scoring rate, so scoring load does not reduce visual smoothness.

### Requirement 2 — Efficient frame handling

**User Story:** As a developer, I want the capture/inference pipeline to avoid unnecessary work, so that the practice loop stays responsive.

#### Acceptance Criteria

1. WHEN frames are passed between threads THEN the system SHALL avoid unnecessary copies of full-resolution frames.
2. WHEN the worker thread produces pose results faster than the UI consumes them THEN the system SHALL keep only the most recent result.
3. WHEN pose detection is running THEN the system SHALL reuse the initialized MediaPipe detector without re-initialization.
4. IF the silhouette render is expensive THEN the system SHALL decouple its update rate from the inference rate so that neither starves the other.
5. WHEN the user is not visible in frame THEN the system SHALL handle the empty pose result gracefully without stalling the loop.

### Requirement 3 — Correct temporal behavior

**User Story:** As a user, I want the scoring to reflect the actual moment of the video I'm dancing to, so that my score is meaningful.

#### Acceptance Criteria

1. WHEN a pose is scored THEN the system SHALL align the user's frame to the reference frame using the video's real playback position (timestamp in milliseconds).
2. WHEN generating timestamps for live pose detection THEN the system SHALL use monotonically increasing values based on real elapsed time, not a fixed per-frame increment.
3. WHEN the video is paused THEN the system SHALL pause scoring but MAY continue updating the live silhouette for positioning feedback.
4. WHEN the video finishes THEN the system SHALL stop scoring and present the final session result.
5. WHEN the video plays at a non-default speed IF speed control exists THEN the alignment SHALL remain consistent with the displayed playback position.

### Requirement 4 — Complete Practice Mode flow

**User Story:** As a user, I want to complete a full practice session from loading a video to seeing my result, so that the MVP is usable end-to-end.

#### Acceptance Criteria

1. WHEN the user launches Practice Mode THEN the system SHALL show the webcam preview and controls to load a video.
2. WHEN the user loads a compatible video THEN the system SHALL analyze it without freezing the UI and report progress or a clear error.
3. WHEN analysis completes THEN the system SHALL enable playback controls (play, pause, restart).
4. WHEN the user plays the video THEN the system SHALL show live accuracy, current grade, and combo updating in real time.
5. WHEN the session ends THEN the system SHALL display the final accuracy and grade.
6. IF the video cannot be opened or analyzed THEN the system SHALL show an understandable message and remain usable.

### Requirement 5 — Correct combo and grading semantics

**User Story:** As a user, I want combo and grades to follow the documented rules, so that the feedback is consistent and fair.

#### Acceptance Criteria

1. WHEN a PERFECT rating occurs THEN the system SHALL increase the combo.
2. WHEN a GREAT rating occurs THEN the system SHALL increase the combo.
3. WHEN an OK rating occurs THEN the system SHALL reset the combo.
4. WHEN a MEH rating occurs THEN the system SHALL reset the combo.
5. WHEN a MISS rating occurs THEN the system SHALL reset the combo.
6. WHEN computing the final grade THEN the system SHALL use the documented accuracy bands (S/A/B/C/D/FAILED) and store continuous numerical accuracy.

### Requirement 6 — Configurable performance settings

**User Story:** As a user on varied hardware, I want to adjust processing quality, so that I can trade accuracy for smoothness when needed.

#### Acceptance Criteria

1. WHEN performance-related values are needed THEN the system SHALL read them from configuration rather than hardcoding them.
2. WHEN the user configures a target processing rate THEN the system SHALL respect it within hardware limits.
3. WHEN camera resolution affects performance THEN the resolution SHALL be configurable.
4. WHEN the scoring rate is configured THEN the system SHALL score at that rate independently of the render rate.
5. IF no user configuration exists THEN the system SHALL use defaults tuned for smooth practice on typical CPUs (high render rate, lower scoring rate).

### Requirement 7 — Stability and resource cleanup

**User Story:** As a user, I want the app to start and close cleanly, so that it does not leak resources or hang.

#### Acceptance Criteria

1. WHEN the Practice Mode window closes THEN the system SHALL stop the camera, release the video player, and terminate worker threads.
2. WHEN a background analysis is running and the window closes THEN the system SHALL stop the analysis without crashing.
3. WHEN the camera fails during a session THEN the system SHALL surface a clear error and stop the loop safely.
4. WHEN the app runs for an extended session THEN the system SHALL NOT accumulate unbounded memory from frames or history.

### Requirement 8 — Non-regression and quality

**User Story:** As a maintainer, I want existing functionality preserved, so that performance work does not break the analysis engine.

#### Acceptance Criteria

1. WHEN this work is complete THEN all existing tests SHALL continue to pass.
2. WHEN Phase 1/2/3/3.5 modules are used THEN their public APIs SHALL remain unchanged unless a change is explicitly justified.
3. WHEN new logic is added THEN it SHALL include unit tests for non-UI, non-hardware logic (timing, frame selection, combo semantics).
4. WHEN the code is checked THEN ruff and mypy SHALL pass with no new errors.
5. WHEN tests run THEN they SHALL NOT require a physical camera or GPU.

## Out of Scope

- Arcade Mode (separate future phase)
- GPU-accelerated inference
- Beat detection / music synchronization
- Advanced ML scoring
- Hand/finger tracking
- Network, cloud, or database features
- Multi-person scoring (subject tracking already selects one person)
