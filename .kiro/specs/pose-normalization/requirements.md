# Requirements Document

## Introduction

This specification defines Phase 2 of OpenDance AI — Pose Normalization, Motion Feature Extraction, and Reference Video Analysis. Phase 2 transforms raw `PoseResult` data from Phase 1 into body-relative normalized coordinates, computes signed joint angles and motion features (velocity via central differences, acceleration, direction), and provides reference video processing with deterministic numerical cache.

Phase 2 does NOT modify Phase 1 components (`PoseResult`, `Landmark`, `WorldLandmark`, `PoseDetector`, `FrameWorker`, `CameraManager`). It consumes `PoseResult` as-is and produces new derived data structures.

Phase 2 does NOT include temporal alignment (DTW), scoring/grading, combo logic, Practice/Arcade modes, new ML models, networking, or database.

## Glossary

- **NormalizedPose**: Body-relative pose representation with translation and scale removed. Contains: `timestamp_ms`, `landmarks_2d`, optional `landmarks_3d`, `visibilities`, `presences`, `body_center`, `body_scale`, `valid` flag.
- **Body_Center**: The midpoint between left hip (landmark 23) and right hip (landmark 24). Computed from world landmarks when available, falling back to image-space landmarks.
- **Body_Scale**: The Euclidean distance between left shoulder (landmark 11) and right hip (landmark 24). Computed from the same coordinate space as Body_Center (world preferred, image fallback).
- **Landmark_Index**: Integer index [0–32] following MediaPipe Pose Landmarker's 33-landmark scheme.
- **JointAngle**: A signed angle (in degrees, range [-180, 180]) at a specific joint, calculated using `atan2(cross, dot)` from three connected landmarks.
- **MotionFeatures**: Per-frame velocity and acceleration for each landmark, computed using central differences for interior frames with forward/backward fallbacks at boundaries.
- **ReferenceAnalyzer**: The module that processes a reference video file to produce a cached sequence of `NormalizedPose` and `MotionFeatures`.
- **AnalysisCache**: A gzipped-JSON-metadata + numpy-savez_compressed file storing derived numerical data. Never stores raw frame pixels. Never uses pickle.
- **Visibility_Threshold**: The minimum `Landmark.visibility` value below which a landmark is treated as unreliable.
- **MissingDataStrategy**: The approach for handling unreliable landmarks. Default: `leave_none` (unreliable landmarks produce `None` in normalized output).

## Requirements

### Requirement 1: Pose Normalization

**User Story:** As a developer, I want to transform raw landmarks into body-relative coordinates, so that poses can be compared independently of camera distance, body position, and body size.

#### Acceptance Criteria

1. THE normalization system SHALL compute Body_Center as the midpoint of landmarks 23 (left hip) and 24 (right hip).
2. THE normalization system SHALL prefer world landmarks (`PoseResult.world_landmarks`) for Body_Center and Body_Scale computation when both required landmarks have visibility >= Visibility_Threshold. IF world landmarks are unavailable or insufficient, THE system SHALL fall back to image-space landmarks (`PoseResult.landmarks`).
3. THE normalization system SHALL compute Body_Scale as the Euclidean distance between landmark 11 (left shoulder) and landmark 24 (right hip), using the same coordinate space selected for Body_Center.
4. THE normalization system SHALL translate all landmark coordinates by subtracting Body_Center, making the body center the origin (0, 0, 0).
5. THE normalization system SHALL scale all translated coordinates by dividing by Body_Scale, producing body-normalized units (dimensionless).
6. IF Body_Scale is below a configurable `min_body_scale` epsilon (default 0.001), THEN normalization SHALL produce a `NormalizedPose` with `valid=False` rather than division-by-zero artifacts.
7. THE normalization system SHALL accept a `PoseResult` as input and produce a `NormalizedPose` as output without modifying the input `PoseResult`.
8. THE normalization system SHALL process 2D image-space landmarks into `landmarks_2d` and 3D world landmarks into `landmarks_3d` (optional, present only when world data is available).
9. THE normalization system SHALL preserve `timestamp_ms` from the input `PoseResult` in the output `NormalizedPose`.
10. THE `NormalizedPose` output SHALL contain separate `visibilities` and `presences` tuples preserving the original per-landmark values from the input `PoseResult`.
11. THE normalization system SHALL be a pure single-frame function. Temporal interpolation is NOT part of `normalize_pose()`.
12. THE normalization system SHALL be independently testable without requiring camera hardware, UI, or MediaPipe.

### Requirement 2: Low-Confidence Landmark Handling

**User Story:** As a developer, I want unreliable landmarks excluded from downstream calculations, so that low-quality detections do not corrupt the analysis.

#### Acceptance Criteria

1. THE normalization system SHALL treat a landmark as unreliable when its `visibility` field (from `Landmark.visibility`) is below the configured Visibility_Threshold.
2. WHEN a landmark is unreliable, THE normalization system SHALL represent its normalized coordinates as `None` in the `NormalizedPose` output (MissingDataStrategy: `leave_none`).
3. IF both Body_Center landmarks (indices 23, 24) are unreliable, THEN normalization SHALL produce a `NormalizedPose` with `valid=False`.
4. IF only one Body_Center landmark is unreliable, THE system SHALL use the available hip landmark as an approximate center.
5. IF the Body_Scale landmarks (indices 11, 24) are both unreliable, THEN normalization SHALL produce a `NormalizedPose` with `valid=False`.
6. THE Visibility_Threshold SHALL be configurable via the configuration system with a default of 0.5.
7. THE normalization system SHALL preserve both `visibility` and `presence` fields in the output without modifying their semantics.

### Requirement 3: Joint Angle Calculation

**User Story:** As a developer, I want to compute signed joint angles from detected poses, so that body configuration can be described numerically for comparison.

#### Acceptance Criteria

1. THE joint angle system SHALL compute signed angles at the following joints: left elbow, right elbow, left shoulder, right shoulder, left knee, right knee, left hip, right hip.
2. EACH computed JointAngle SHALL use the `atan2(cross, dot)` formula producing signed angles in degrees in the range [-180, 180].
3. IF any of the three landmarks required for a joint angle has `visibility` below the Visibility_Threshold, THEN that JointAngle SHALL be `None`.
4. THE joint angle calculation SHALL use normalized 3D coordinates from `NormalizedPose.landmarks_3d` when available, falling back to `landmarks_2d`.
5. THE joint angle system SHALL be a pure function: input is `NormalizedPose`, output is a mapping of joint names to angles (or `None`).
6. THE joint angle system SHALL be independently testable with synthetic landmark data.

### Requirement 4: Motion Feature Extraction

**User Story:** As a developer, I want to compute velocity, acceleration, and movement direction from pose sequences, so that movement dynamics can be analyzed.

#### Acceptance Criteria

1. THE motion feature system SHALL compute per-landmark velocity using central differences for interior frames: `v[i] = (pos[i+1] - pos[i-1]) / (2 * dt)`, with forward difference at the start and backward difference at the end of the sequence.
2. THE motion feature system SHALL compute per-landmark acceleration using central differences on velocity: `a[i] = (v[i+1] - v[i-1]) / (2 * dt)`, with forward/backward fallbacks at boundaries.
3. THE motion feature system SHALL compute per-landmark movement direction as the normalized displacement vector between consecutive frames.
4. THE motion feature system SHALL derive time delta from `timestamp_ms` differences: `dt = (timestamp_ms[i+1] - timestamp_ms[i]) / 1000.0` seconds.
5. THE motion feature system SHALL express velocity in body-normalized units per second and acceleration in body-normalized units per second squared.
6. IF a landmark is `None` in any frame required for the difference calculation, THEN velocity, acceleration, and direction for that landmark SHALL be `None`.
7. IF the time delta between required frames is zero, THEN motion features for that frame SHALL be `None`.
8. THE motion feature system SHALL require a sequence of at least two `NormalizedPose` frames to produce any velocity and at least three for acceleration via central differences.
9. THE `MotionFeatures` output SHALL be a frozen dataclass containing per-landmark velocity, acceleration, direction, `timestamp_ms`, and `dt_seconds`.
10. THE motion feature system SHALL be independently testable with synthetic pose sequences.

### Requirement 5: Reference Video Processing

**User Story:** As a user, I want to import and analyze a reference dance video, so that the system can extract its motion data for future comparison.

#### Acceptance Criteria

1. THE ReferenceAnalyzer SHALL accept a local filesystem video file path and process the video to extract pose data.
2. THE ReferenceAnalyzer SHALL use OpenCV VideoCapture for video frame extraction.
3. THE ReferenceAnalyzer SHALL use `PoseDetector.detect(frame, timestamp_ms)` from Phase 1 for pose detection. The existing `PoseDetector` SHALL NOT be modified.
4. THE ReferenceAnalyzer SHALL use deterministic sampling based on configured FPS: frames are sampled at regular intervals (e.g., every 33ms for 30fps) and each sample receives its authoritative `timestamp_ms` passed to `PoseDetector.detect()`.
5. THE ReferenceAnalyzer SHALL compute `NormalizedPose` for each detected frame.
6. THE ReferenceAnalyzer SHALL compute `MotionFeatures` for the full sequence using central differences.
7. THE ReferenceAnalyzer SHALL produce a complete `ReferenceSequence` containing all normalized poses, motion features, and joint angles with timestamps.
8. THE ReferenceAnalyzer SHALL handle frames where no pose is detected by inserting `None` entries in the sequence.
9. THE ReferenceAnalyzer SHALL extract video metadata: total frames, FPS, duration, resolution.
10. THE ReferenceAnalyzer SHALL NOT block the UI thread.
11. THE ReferenceAnalyzer SHALL log progress without logging frame pixel data.

### Requirement 6: Analysis Cache

**User Story:** As a user, I want reference video analysis results cached, so that I don't have to re-analyze the same video every time.

#### Acceptance Criteria

1. THE AnalysisCache SHALL store derived numerical data using gzipped JSON for metadata and `numpy.savez_compressed` for numeric arrays.
2. THE AnalysisCache SHALL NOT store raw video frames, images, or pickle-serialized objects.
3. THE AnalysisCache SHALL identify cached results by: absolute video file path, file modification timestamp (mtime), relevant configuration hash, and model-file metadata (path + mtime of the `.task` file).
4. IF the source video file mtime changes, THEN the cache SHALL be considered invalid.
5. IF the model file metadata changes, THEN the cache SHALL be considered invalid.
6. IF the relevant configuration values change (normalization + motion config hash), THEN the cache SHALL be considered invalid.
7. THE AnalysisCache SHALL be disabled by default (`auto_cache = false`).
8. THE AnalysisCache SHALL store cache files in a configurable directory.
9. THE AnalysisCache SHALL validate integrity on load. Corrupted or incompatible cache SHALL be discarded.
10. THE AnalysisCache SHALL be independently testable without real video files or MediaPipe.

### Requirement 7: Landmark Index Mapping

**User Story:** As a developer, I want a named mapping for MediaPipe landmark indices, so that code references landmarks by anatomical name.

#### Acceptance Criteria

1. THE system SHALL provide module-level integer constants mapping landmark index [0–32] to anatomical name.
2. THE mapping SHALL be consistent with MediaPipe Pose Landmarker's 33-landmark scheme.
3. THE mapping SHALL define which landmark triplets form each computable joint angle.
4. THE mapping SHALL be importable by normalization, joint angle, motion feature, and skeleton renderer modules.

### Requirement 8: Configuration Extension

**User Story:** As a developer, I want Phase 2 settings managed through the existing configuration system.

#### Acceptance Criteria

1. THE configuration system SHALL be extended with `[normalization]` containing: `enabled` (bool, default: false), `visibility_threshold` (float, default: 0.5), `min_body_scale` (float, default: 0.001), `missing_data_strategy` (str, default: "leave_none").
2. THE configuration system SHALL be extended with `[motion]` containing: `min_velocity_threshold` (float, default: 0.01).
3. THE configuration system SHALL be extended with `[reference]` containing: `cache_directory` (str, default: ""), `auto_cache` (bool, default: false), `sample_fps` (float, default: 30.0).
4. THE AppConfig dataclass SHALL be extended with new frozen dataclass fields following the existing pattern.
5. Existing `[scoring]`, `[camera]`, and `[pose]` sections SHALL NOT be modified.
6. Validation SHALL follow the same patterns as Phase 0/1 (type check, range, fallback with warning).

### Requirement 9: Phase 2 Scope Boundaries

**User Story:** As a developer, I want explicit Phase 2 boundaries.

#### Acceptance Criteria

1. Phase 2 SHALL NOT implement temporal alignment (DTW or equivalent).
2. Phase 2 SHALL NOT implement scoring, grading, combo, or event rating.
3. Phase 2 SHALL NOT implement Practice or Arcade mode.
4. Phase 2 SHALL NOT introduce new ML models.
5. Phase 2 SHALL NOT introduce networking, cloud, or database.
6. Phase 2 SHALL NOT modify `PoseResult`, `Landmark`, `WorldLandmark`, or `PoseDetector`.
7. Phase 2 SHALL NOT modify `FrameWorker` or `CameraManager`.
8. Phase 2 SHALL maintain full backward compatibility — all existing Phase 1 tests MUST pass.
9. FrameWorker integration (if included) SHALL be optional and feature-flagged, not mandatory for core Phase 2.

### Requirement 10: Testability

**User Story:** As a developer, I want Phase 2 testable without hardware.

#### Acceptance Criteria

1. ALL Phase 2 modules SHALL be testable with synthetic `PoseResult` data.
2. Unit tests SHALL NOT require camera, GPU, or model files.
3. Reference video tests SHALL use synthetic videos or mocked VideoCapture.
4. Property-based tests (hypothesis) SHALL cover normalization math, angle calculation, and motion features.
5. Boundary conditions SHALL be tested: zero body scale, identical timestamps, single-frame sequences, all-None landmarks.
