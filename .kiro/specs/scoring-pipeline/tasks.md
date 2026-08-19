# Implementation Plan: Scoring Pipeline (Phase 3)

## Overview

Phase 3 implements temporal alignment (nearest-frame), per-frame comparison (pose 2D x/y, signed angles with wraparound, speed+direction motion, phase-alignment timing), aggregation, event rating, and structured feedback. All modules are pure functions. No DTW, no ML, no UI coupling.

## Tasks

- [x] 1. Extend configuration for Phase 3
  - [x] 1.1 Add ComparisonConfig dataclass and extend AppConfig
    - `ComparisonConfig(pose_scale_factor=200.0, angle_scale=1.0, timing_scale=0.5, min_valid_landmarks=8, feedback_significance_threshold=0.1, motion_speed_weight=0.5, motion_direction_weight=0.5, epsilon=0.001)`
    - Extend `AppConfig` with `comparison_config` field
    - **Files:** `src/opendance/config/models.py`, `src/opendance/config/__init__.py`
    - _Requirements: 11.1, 11.3_

  - [x] 1.2 Extend defaults.toml with [scoring.comparison]
    - **Files:** `src/opendance/config/defaults.toml`
    - _Requirements: 11.1_

  - [x] 1.3 Extend loader.py validation for comparison config
    - All values > 0 for scale factors, [0,1] for weights/threshold, epsilon > 0, min_valid_landmarks >= 1
    - **Files:** `src/opendance/config/loader.py`
    - _Requirements: 11.3_

  - [x]* 1.4 Write config tests
    - Defaults, overrides, invalid fallback
    - **Files:** `tests/unit/test_config_phase3.py`
    - _Requirements: 11.1, 14.1_

- [x] 2. Implement scoring data models and LANDMARK_REGIONS
  - [x] 2.1 Create models.py with EventRating, FrameComparison, FeedbackItem, LANDMARK_REGIONS
    - LANDMARK_REGIONS maps all 33 indices to: "face", "left_arm", "right_arm", "torso", "left_leg", "right_leg"
    - **Files:** `src/opendance/scoring/models.py`, `src/opendance/scoring/__init__.py`
    - _Requirements: 7.1, 8.1, 8.2, 9.1, 9.2, 9.3_

- [x] 3. Implement temporal alignment
  - [x] 3.1 Create alignment.py with align_frame()
    - Nearest-frame, no interpolation, clamped boundaries, deterministic
    - Formula: `round(clamp(player_ts / ref_duration, 0, 1) * (N-1))`
    - **Files:** `src/opendance/scoring/alignment.py`, `src/opendance/scoring/__init__.py`
    - _Requirements: 1.1–1.7_

  - [x]* 3.2 Write alignment tests
    - Boundaries, midpoint, outside range, determinism
    - **Files:** `tests/unit/test_alignment.py`
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 14.2_

- [x] 4. Implement pose comparison
  - [x] 4.1 Create pose_compare.py with compute_pose_score()
    - 2D (x,y) Euclidean distance only. z excluded.
    - `max(0, 100 - mean_dist * scale_factor)`
    - None exclusion, min_valid_landmarks threshold
    - **Files:** `src/opendance/scoring/pose_compare.py`, `src/opendance/scoring/__init__.py`
    - _Requirements: 2.1–2.7_

  - [x]* 4.2 Write pose comparison tests
    - Identical → 100, max divergence → 0, partial None, < min landmarks → None
    - **Files:** `tests/unit/test_pose_compare.py`
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 14.2, 14.4_

- [x] 5. Implement angle comparison
  - [x] 5.1 Create angle_compare.py with compute_angle_score()
    - Circular error: `min(abs_diff, 360 - abs_diff)`
    - `max(0, 100 - mean_error * angle_scale)`
    - **Files:** `src/opendance/scoring/angle_compare.py`, `src/opendance/scoring/__init__.py`
    - _Requirements: 3.1–3.6_

  - [x]* 5.2 Write angle comparison tests
    - Zero error → 100, wraparound (-179 vs +179 → error 2°), all None → None
    - **Files:** `tests/unit/test_angle_compare.py`
    - _Requirements: 3.1, 3.2, 3.5, 14.2_

- [x] 6. Checkpoint — verify comparison modules
  - Run pytest, ruff, mypy. Verify 192 existing tests pass.

- [x] 7. Implement motion comparison
  - [x] 7.1 Create motion_compare.py with compute_motion_score()
    - Speed sim: `1 - abs(p-r)/max(p,r,eps)`. Both below eps → 1.0.
    - Direction sim: `max(0, dot(p_dir, r_dir))`. Undefined when speed < eps → use speed only.
    - `mean(per_lm) * 100`
    - **Files:** `src/opendance/scoring/motion_compare.py`, `src/opendance/scoring/__init__.py`
    - _Requirements: 4.1–4.10_

  - [x]* 7.2 Write motion comparison tests
    - Identical motion → 100, opposite direction → low, zero speed → speed_sim only, None → None
    - **Files:** `tests/unit/test_motion_compare.py`
    - _Requirements: 4.1, 4.2, 4.3, 4.7, 4.8, 14.2_

- [x] 8. Implement timing comparison
  - [x] 8.1 Create timing_compare.py with compute_timing_score()
    - Phase alignment: same state → 100, mismatch → penalty
    - `max(0, 100 - moving_speed * timing_scale * 1000)`
    - Averaged per-landmark
    - **Files:** `src/opendance/scoring/timing_compare.py`, `src/opendance/scoring/__init__.py`
    - _Requirements: 5.1–5.9_

  - [x]* 8.2 Write timing comparison tests
    - Both moving → 100, both still → 100, mismatch → penalty, None → None
    - **Files:** `tests/unit/test_timing_compare.py`
    - _Requirements: 5.1, 5.3, 5.4, 5.7, 14.2_

- [x] 9. Implement aggregation and rating
  - [x] 9.1 Create aggregation.py with aggregate_scores()
    - Uses existing ScoringWeights. Renormalize for None. [0,100] or None.
    - **Files:** `src/opendance/scoring/aggregation.py`, `src/opendance/scoring/__init__.py`
    - _Requirements: 6.1–6.5_

  - [x] 9.2 Create rating.py with compute_event_rating()
    - Uses existing ScoringThresholds. None → MISS.
    - **Files:** `src/opendance/scoring/rating.py`, `src/opendance/scoring/__init__.py`
    - _Requirements: 7.1–7.4_

  - [x]* 9.3 Write aggregation and rating tests
    - Renormalization, all None → None, threshold boundaries (89.99→GREAT, 90→PERFECT)
    - **Files:** `tests/unit/test_aggregation.py`
    - _Requirements: 6.2, 6.3, 7.1, 7.2, 7.3, 14.2_

- [x] 10. Implement feedback generation
  - [x] 10.1 Create feedback.py with generate_feedback()
    - Angle severity: `min(1, error/90)`. Pose severity: `min(1, dist/0.5)`.
    - Only emit if severity > significance_threshold.
    - body_region from LANDMARK_REGIONS.
    - **Files:** `src/opendance/scoring/feedback.py`, `src/opendance/scoring/__init__.py`
    - _Requirements: 8.1–8.8_

  - [x]* 10.2 Write feedback tests
    - Above threshold emitted, below filtered, correct body_region, measurable descriptions
    - **Files:** `tests/unit/test_feedback.py`
    - _Requirements: 8.1, 8.4, 8.5, 14.1_

- [x] 11. Implement ScoringEngine orchestrator
  - [x] 11.1 Create engine.py with ScoringEngine
    - score_frame(): align → compare → aggregate → rate → feedback
    - score_sequence(): full sequence scoring
    - **Files:** `src/opendance/scoring/engine.py`, `src/opendance/scoring/__init__.py`
    - _Requirements: 1.1, 12.1, 12.2_

  - [x]* 11.2 Write engine integration tests
    - Full pipeline with synthetic data. Determinism. Missing data.
    - **Files:** `tests/unit/test_scoring_engine.py`
    - _Requirements: 12.1, 12.2, 10.1, 14.1_

- [x] 12. Final checkpoint
  - ALL existing 192 tests pass unchanged
  - ALL Phase 3 tests pass
  - ruff, mypy clean
  - No Phase 1/2 files modified except config (additive only)

## Notes

- All scoring modules are pure functions.
- No DTW. Nearest-frame alignment only.
- No landmark interpolation between reference frames.
- Pose comparison uses 2D (x,y) only. z excluded.
- Motion comparison excludes acceleration.
- Timing is phase-alignment, not peak detection.
- Direction similarity clamped [0,1]. Opposite → 0.
- Existing ScoringThresholds and ScoringWeights consumed directly.
- Feedback severity: angle=error/90, pose=dist/0.5, capped [0,1].
- LANDMARK_REGIONS maps all 33 indices to 6 body regions.
- All tests synthetic — no hardware required.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["1.4", "2.1"] },
    { "id": 3, "tasks": ["3.1", "4.1", "5.1"] },
    { "id": 4, "tasks": ["3.2", "4.2", "5.2", "7.1"] },
    { "id": 5, "tasks": ["7.2", "8.1"] },
    { "id": 6, "tasks": ["8.2", "9.1", "9.2"] },
    { "id": 7, "tasks": ["9.3", "10.1"] },
    { "id": 8, "tasks": ["10.2", "11.1"] },
    { "id": 9, "tasks": ["11.2"] }
  ]
}
```
