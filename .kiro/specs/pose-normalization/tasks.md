# Implementation Plan: Pose Normalization & Motion Features (Phase 2)

## Overview

Phase 2 implements pose normalization (world-preferred, image-fallback), signed joint angles (atan2), motion features (central differences), reference video analysis (deterministic sampling), and numerical cache (gzip JSON + numpy). All tasks consume Phase 1 API unchanged.

## Tasks

- [ ] 1. Extend configuration system for Phase 2
  - [x] 1.1 Add NormalizationConfig, MotionConfig, ReferenceConfig dataclasses
    - `NormalizationConfig(enabled=False, visibility_threshold=0.5, min_body_scale=0.001, missing_data_strategy="leave_none")`
    - `MotionConfig(min_velocity_threshold=0.01)`
    - `ReferenceConfig(cache_directory="", auto_cache=False, sample_fps=30.0)`
    - Extend `AppConfig` with three new fields
    - Update `src/opendance/config/__init__.py` exports
    - **Files:** `src/opendance/config/models.py`, `src/opendance/config/__init__.py`
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 1.2 Extend defaults.toml with [normalization], [motion], [reference]
    - **Files:** `src/opendance/config/defaults.toml`
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 1.3 Extend loader.py to validate Phase 2 config sections
    - enabled (bool), visibility_threshold [0.0, 1.0], min_body_scale > 0, missing_data_strategy in {"leave_none"}, min_velocity_threshold >= 0, auto_cache (bool), sample_fps > 0
    - **Files:** `src/opendance/config/loader.py`
    - _Requirements: 8.5, 8.6_

  - [x]* 1.4 Write config extension tests
    - Defaults load correctly, partial overrides merge, invalid values fall back
    - **Files:** `tests/unit/test_config_phase2.py`
    - _Requirements: 8.6, 10.1_

- [ ] 2. Implement landmark index constants
  - [x] 2.1 Create landmarks.py
    - All 33 constants, JOINT_ANGLES dict, BODY_CENTER_LANDMARKS, BODY_SCALE_LANDMARKS
    - **Files:** `src/opendance/motion/landmarks.py`, `src/opendance/motion/__init__.py`
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ] 3. Implement NormalizedPose data model
  - [x] 3.1 Create normalized_pose.py
    - Frozen dataclass with: timestamp_ms, landmarks_2d, landmarks_3d (optional), visibilities, presences, body_center, body_scale, valid
    - Include `invalid()` factory method
    - **Files:** `src/opendance/motion/normalized_pose.py`, `src/opendance/motion/__init__.py`
    - _Requirements: 1.8, 1.9, 1.10, 2.2, 2.7_

- [ ] 4. Implement pose normalizer
  - [x] 4.1 Create normalizer.py with normalize_pose()
    - Pure single-frame function: PoseResult + NormalizationConfig → NormalizedPose
    - World-landmark preference for center/scale when visibility sufficient
    - Image-space fallback when world landmarks unavailable
    - Body center from landmarks 23/24 (midpoint or single-hip fallback)
    - Body scale from landmarks 11/24; fail if < min_body_scale
    - leave_none strategy for low-visibility landmarks
    - Preserve original visibilities and presences in output
    - **Files:** `src/opendance/motion/normalizer.py`, `src/opendance/motion/__init__.py`
    - _Requirements: 1.1–1.12, 2.1–2.7_

  - [x]* 4.2 Write normalization property tests
    - Property 1: translation removal (center → origin)
    - Property 2: scale removal (shoulder-hip distance → 1.0)
    - Property 5: None propagation for low-visibility
    - Property 7: world-landmark preference
    - Edge cases: zero scale, one hip missing, all None, no world landmarks
    - **Files:** `tests/unit/test_normalizer.py`
    - _Requirements: 1.1–1.6, 2.1–2.5, 10.4, 10.5_

- [ ] 5. Implement signed joint angles
  - [x] 5.1 Create angles.py with compute_joint_angles()
    - atan2(cross, dot) formula → signed degrees [-180, 180]
    - Use landmarks_3d when available, fallback to landmarks_2d
    - None for joints with any missing landmark
    - **Files:** `src/opendance/motion/angles.py`, `src/opendance/motion/__init__.py`
    - _Requirements: 3.1–3.6_

  - [x]* 5.2 Write joint angle property tests
    - Property 3: angle always in [-180, 180]
    - Known configs: right angle (90°), straight (180°/-180°), negative angles
    - None propagation when landmarks missing
    - **Files:** `tests/unit/test_angles.py`
    - _Requirements: 3.1–3.3, 10.4_

- [ ] 6. Checkpoint — verify normalization layer
  - Run pytest, ruff, mypy. Verify 111+ existing tests pass.

- [ ] 7. Implement motion features (central differences)
  - [x] 7.1 Create motion_result.py with LandmarkMotion and MotionFeatures
    - Frozen dataclasses per design
    - **Files:** `src/opendance/motion/motion_result.py`, `src/opendance/motion/__init__.py`
    - _Requirements: 4.9_

  - [x] 7.2 Create features.py with compute_sequence_motion()
    - Accepts full sequence of NormalizedPose | None
    - Central differences for interior frames
    - Forward/backward differences at boundaries
    - timestamp_ms → seconds conversion inside function
    - None propagation for missing landmarks and zero dt
    - Velocity in body-normalized units/sec, acceleration in units/sec²
    - **Files:** `src/opendance/motion/features.py`, `src/opendance/motion/__init__.py`
    - _Requirements: 4.1–4.10_

  - [x]* 7.3 Write motion feature tests
    - Property 4: central-difference velocity = (p2-p0)/(2*dt) for known sequences
    - Test boundary handling (forward/backward at edges)
    - Test zero dt → None
    - Test None propagation
    - Test minimum 2 frames for velocity, 3 for acceleration
    - **Files:** `tests/unit/test_motion_features.py`
    - _Requirements: 4.1, 4.6, 4.7, 4.8, 10.4, 10.5_

- [ ] 8. Implement reference video analysis
  - [x] 8.1 Create reference_sequence.py with VideoMetadata and ReferenceSequence
    - Frozen dataclasses
    - **Files:** `src/opendance/video/reference_sequence.py`, `src/opendance/video/__init__.py`
    - _Requirements: 5.7, 5.9_

  - [x] 8.2 Create reference_analyzer.py with ReferenceAnalyzer
    - Deterministic sampling at configured sample_fps
    - Authoritative timestamp_ms = sample_index * (1000 / sample_fps)
    - PoseDetector.detect(frame, timestamp_ms) called with authoritative timestamp
    - normalize + angles per frame, then compute_sequence_motion on full sequence
    - Local filesystem paths only
    - **Files:** `src/opendance/video/reference_analyzer.py`, `src/opendance/video/__init__.py`
    - _Requirements: 5.1–5.11_

  - [x]* 8.3 Write reference analyzer tests (mocked)
    - Synthetic 5-frame mock video
    - No-detection frames → None entries
    - Metadata extraction
    - Deterministic timestamp assignment
    - **Files:** `tests/unit/test_reference_analyzer.py`
    - _Requirements: 5.1, 5.4, 5.8, 10.2, 10.3_

- [ ] 9. Implement analysis cache
  - [x] 9.1 Create analysis_cache.py
    - Gzipped JSON metadata + numpy.savez_compressed numeric arrays
    - Cache key: abs video path + mtime + config hash + model file (path+mtime)
    - No pickle, no frames
    - Disabled by default (auto_cache=False)
    - Validation on load, discard on corruption
    - **Files:** `src/opendance/video/analysis_cache.py`, `src/opendance/video/__init__.py`
    - _Requirements: 6.1–6.10_

  - [x]* 9.2 Write cache tests
    - Write/read round-trip
    - Invalidation on video mtime change
    - Invalidation on config hash change
    - Invalidation on model file mtime change
    - Corrupted cache → discard
    - Property 6: deterministic output
    - **Files:** `tests/unit/test_analysis_cache.py`
    - _Requirements: 6.1, 6.3–6.6, 6.9, 10.1_

- [x] 10. Final checkpoint
  - ALL existing Phase 1 tests (111) must pass unchanged
  - ALL new Phase 2 tests must pass
  - `ruff check src/ tests/`
  - `mypy src/`
  - No Phase 1 files modified (except config/models.py, config/defaults.toml, config/loader.py, config/__init__.py — additive only)

## Notes

- Phase 1 API (`PoseResult`, `PoseDetector`, `FrameWorker`, `CameraManager`) is NOT modified.
- Joint angles use atan2(cross, dot) → [-180, 180], NOT arccos → [0, 180].
- Motion uses central differences on the full sequence, NOT simple backward differences.
- timestamp_ms is the authoritative time source. No wall-clock dependency.
- Cache uses gzip JSON + numpy.savez_compressed. Never pickle. Never frames.
- Cache disabled by default (auto_cache = false).
- Normalization disabled by default (enabled = false).
- FrameWorker integration is out of scope for core Phase 2 (optional, feature-flagged if added).
- Body center/scale prefer world landmarks when available; fall back to image-space.
- All tests use synthetic data — no camera, GPU, or model required.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["1.4", "2.1", "3.1"] },
    { "id": 3, "tasks": ["4.1"] },
    { "id": 4, "tasks": ["4.2", "5.1"] },
    { "id": 5, "tasks": ["5.2", "7.1"] },
    { "id": 6, "tasks": ["7.2"] },
    { "id": 7, "tasks": ["7.3", "8.1"] },
    { "id": 8, "tasks": ["8.2"] },
    { "id": 9, "tasks": ["8.3", "9.1"] },
    { "id": 10, "tasks": ["9.2"] }
  ]
}
```
