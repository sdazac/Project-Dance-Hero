# Requirements: Practice Mode I/O Controls (Camera Management + Analysis Progress)

## Introduction

Practice Mode needs a usable, self-explanatory interface for the two inputs a
user must manage: the **webcam** and the **reference video**. Today the camera
starts on a single hardcoded device index with no way to restart it or switch to
another camera, and video analysis (which is slow — several seconds to minutes)
shows only an indeterminate "Analyzing..." overlay with no sense of remaining
time.

This spec adds:
- Camera controls: restart the camera and change the input device (port/index),
  with clear status and error messaging.
- Video analysis progress: a percentage progress bar so the user can gauge how
  much of the analysis remains.

All changes align with `product.md` (MVP steps 2–7: grant camera access, see the
feed, import and analyze a video with progress or a clear error), `architecture.md`
(camera layer owns camera lifecycle; UI stays thin; no UI-thread blocking), and
`privacy.md` (local processing, clear permission/error messaging).

## Glossary

- **Device index**: the OpenCV `VideoCapture` integer index identifying a camera
  (0 = default). "Changing port" means selecting a different device index.
- **Camera restart**: releasing the current capture/worker and re-opening the
  camera (same or new device index) without restarting the app.
- **Analysis progress**: fraction of reference-video samples processed, reported
  as an integer percentage 0–100.

## Requirements

### Requirement 1 — Restart the camera

**User Story:** As a user whose camera froze or was unplugged, I want to restart
it without closing the app, so I can recover the live feed.

#### Acceptance Criteria

1. WHEN the user requests a camera restart THEN the system SHALL stop the current
   camera (release capture, terminate the frame worker) and start it again using
   the current device index.
2. WHEN the camera restarts successfully THEN the live feed and pose overlay
   SHALL resume without requiring an application restart.
3. WHEN a restart fails (device unavailable) THEN the system SHALL surface a
   clear, user-facing error and remain responsive (no crash, no hang).
4. WHEN a restart occurs THEN existing cleanup guarantees SHALL hold (no leaked
   capture handles or worker threads).

### Requirement 2 — Change the camera input device (port)

**User Story:** As a user with multiple cameras, I want to pick which camera to
use, so I can select the correct input.

#### Acceptance Criteria

1. WHEN the user selects a different device index THEN the system SHALL restart
   the camera on that index.
2. WHEN a new device index is applied THEN subsequent live frames SHALL come from
   that device.
3. WHEN the selected device cannot be opened THEN the system SHALL show a clear
   error and leave the app usable (the user can pick another index).
4. WHEN the device index control is presented THEN it SHALL cover a sane range of
   indices (e.g. 0–9) and default to the configured `camera.device_index`.
5. WHEN the device index is changed THEN the change SHALL be applied via the
   camera layer (CameraManager), not by reaching into OpenCV from the UI
   (architecture: camera layer owns camera lifecycle).

### Requirement 3 — Camera status feedback

**User Story:** As a user, I want to see whether the camera is active, starting,
or in error, so I understand what's happening.

#### Acceptance Criteria

1. WHEN the camera changes state (active, error, inactive) THEN the UI SHALL
   reflect it in a visible status indication.
2. WHEN the camera is in error THEN the message SHALL be understandable and the
   controls to restart / change device SHALL remain usable.
3. WHEN the camera is starting/restarting THEN controls that could conflict
   (e.g. repeated restart spam) MAY be briefly disabled to prevent races, then
   re-enabled.

### Requirement 4 — Video analysis progress bar

**User Story:** As a user importing a dance video, I want a percentage progress
bar during analysis, so I can estimate how long it will take.

#### Acceptance Criteria

1. WHEN reference-video analysis starts THEN the UI SHALL show a progress
   indicator initialized at 0%.
2. WHEN analysis processes samples THEN the progress indicator SHALL update
   toward 100% in a monotonically non-decreasing manner reflecting the fraction
   of samples processed.
3. WHEN analysis completes THEN the progress indicator SHALL reach 100% and then
   be hidden/replaced by the ready state (playback enabled).
4. WHEN analysis runs THEN progress updates SHALL NOT block or freeze the UI
   thread (analysis stays on the worker thread; only progress values cross to
   the UI thread).
5. WHEN analysis fails THEN the progress indicator SHALL be replaced by a clear
   error message and the app SHALL remain usable.
6. WHEN the analyzer reports progress THEN it SHALL do so through an optional,
   additive callback so the analyzer remains usable without a UI and its public
   behavior is unchanged when no callback is provided.

### Requirement 5 — Progress reporting is testable and non-invasive

**User Story:** As a maintainer, I want progress reporting unit-tested without a
real video or GUI.

#### Acceptance Criteria

1. WHEN `ReferenceAnalyzer.analyze` is given a progress callback THEN it SHALL
   invoke the callback with (processed_count, total_count) or an equivalent that
   lets the caller compute a percentage, at a bounded frequency.
2. WHEN no callback is provided THEN `analyze` SHALL behave exactly as before
   (backward compatible; existing tests unaffected).
3. WHEN progress percentage is computed from counts THEN the mapping SHALL be a
   pure, unit-testable function (0 total → 0%, clamped to [0, 100],
   non-decreasing).
4. WHEN the worker emits progress THEN it SHALL be via a Qt signal so the UI
   updates on the UI thread.

### Requirement 6 — Integration with existing Practice Mode

**User Story:** As a user, I want the new controls to fit the existing flow.

#### Acceptance Criteria

1. WHEN controls are added THEN existing play/pause/restart, timers, scoring, and
   cleanup behavior SHALL be preserved.
2. WHEN a camera restart/device change happens mid-session THEN the live pose
   buffer SHALL be cleared (a camera change is a discontinuity) and scoring
   SHALL continue safely once frames resume.
3. WHEN the window closes THEN all cleanup (timers, player, worker, camera)
   SHALL remain correct.

### Requirement 7 — Configuration and defaults

**User Story:** As a user on varied hardware, I want camera settings configurable.

#### Acceptance Criteria

1. WHEN the device index range is needed THEN its maximum SHALL be reasonable and
   MAY be derived from a small constant (e.g. indices 0–9); the initial value
   SHALL come from `camera.device_index` config.
2. WHEN camera resolution matters THEN it SHALL remain configurable via existing
   `[camera]` config (unchanged).

### Requirement 8 — Non-regression and quality

**User Story:** As a maintainer, I want existing functionality preserved.

#### Acceptance Criteria

1. WHEN this work is complete THEN all existing tests SHALL pass.
2. WHEN inspected THEN existing public APIs SHALL remain backward compatible
   (analyzer progress is additive; camera gains a restart/set-device method).
3. WHEN ruff and mypy run THEN they SHALL report no new errors.
4. WHEN tests run THEN they SHALL NOT require a physical camera, GPU, or real
   video (mock capture / analyzer; offscreen Qt).

## Out of Scope

- Enumerating human-readable camera names (OpenCV lacks a portable API); the
  device selector uses integer indices.
- Cloud/network features, recording camera video, changing the analysis
  algorithm.
- Playback seek/speed controls (covered by the separate
  `practice-playback-controls` spec).
