# Requirements Document

## Introduction

This specification defines Phase 3 of OpenDance AI — the Scoring Pipeline. Phase 3 compares a player's normalized pose and motion data against a precomputed reference sequence and produces deterministic, explainable scores with structured feedback.

Phase 3 builds on Phase 2's `NormalizedPose`, `MotionFeatures`, `compute_joint_angles()`, and `ReferenceSequence` without modifying them. It introduces temporal alignment (nearest-frame), per-frame comparison (pose 2D x/y, signed angles with wraparound, speed+direction motion, phase-alignment timing), score aggregation, event rating, and structured feedback.

Phase 3 does NOT implement Practice/Arcade mode UI, combo logic, final grading, DTW, advanced ML scoring, peak timing detection, choreography segmentation, music synchronization, cloud services, or database storage.

## Glossary

- **Alignment_Strategy**: Nearest-frame mapping from player timestamp to reference frame index using timestamp ratios. No interpolation of landmark positions.
- **FrameComparison**: The result of comparing one player frame against its aligned reference frame, containing pose, angle, motion, and timing sub-scores.
- **PoseScore**: 2D (x, y only) landmark distance similarity [0–100]. z-component excluded.
- **AngleScore**: Signed-angle circular error similarity [0–100]. Wraparound-correct.
- **MotionScore**: Speed magnitude + direction (dot product, clamped [0,1]) similarity [0–100]. Acceleration excluded.
- **TimingScore**: Movement-phase alignment metric [0–100]. Both moving or both still = full credit. Mismatch = penalty.
- **CombinedScore**: Weighted aggregation of available sub-scores using existing `ScoringWeights` [0–100].
- **EventRating**: Categorical rating (PERFECT, GREAT, OK, MEH, MISS) from `ScoringThresholds`.
- **ScoringFeedback**: Structured `FeedbackItem` list with body region, issue type, severity [0–1], measurable description.
- **LANDMARK_REGIONS**: Mapping from landmark indices to body-region names for feedback.

## Requirements

### Requirement 1: Temporal Alignment

**User Story:** As a developer, I want the system to map player timestamps to reference frame positions, so that comparison happens at corresponding moments in the choreography.

#### Acceptance Criteria

1. THE alignment SHALL compute a reference frame index from: `nearest_frame = round(player_timestamp_ms / reference_duration_ms * (reference_frame_count - 1))`, clamped to [0, reference_frame_count - 1].
2. THE alignment SHALL select the single nearest reference frame. Landmark-position interpolation between adjacent frames SHALL NOT be performed in Phase 3.
3. THE alignment SHALL produce deterministic output: same inputs → same frame index.
4. IF `player_timestamp_ms < 0`, THEN alignment SHALL clamp to frame index 0.
5. IF `player_timestamp_ms > reference_duration_ms`, THEN alignment SHALL clamp to the last frame index.
6. THE alignment SHALL be a pure function with no side effects.
7. Landmark-position interpolation is explicitly deferred to a future phase due to None-handling complexity.

### Requirement 2: Pose Comparison

**User Story:** As a developer, I want to compare normalized 2D landmark positions between player and reference to measure spatial accuracy.

#### Acceptance Criteria

1. THE pose comparison SHALL compute per-landmark Euclidean distance using only x and y coordinates from `NormalizedPose.landmarks_2d`. The z-component SHALL NOT be included in the Phase 3 distance calculation.
2. THE pose comparison SHALL exclude landmark pairs where either player or reference value is `None`.
3. THE pose comparison SHALL compute PoseScore as `max(0.0, 100.0 - mean_distance * pose_scale_factor)` where mean_distance is the mean of valid per-landmark 2D Euclidean distances.
4. `pose_scale_factor` SHALL be configurable with a default of 200.0. This means 0.5 body-normalized units mean distance produces score 0.
5. IF fewer than `min_valid_landmarks` (default 8) landmark pairs are available, THEN PoseScore SHALL be `None`.
6. THE pose comparison SHALL be a pure function, independently testable.
7. `landmarks_3d` is available in the data model but NOT consumed by the Phase 3 pose comparison.

### Requirement 3: Joint-Angle Comparison

**User Story:** As a developer, I want to compare signed joint angles with correct wraparound handling.

#### Acceptance Criteria

1. THE angle comparison SHALL compute per-joint circular angular error: `error = min(abs(player - reference), 360 - abs(player - reference))` for angles in [-180, 180].
2. THE angle comparison SHALL exclude joints where either player or reference angle is `None`.
3. THE angle comparison SHALL compute AngleScore as `max(0.0, 100.0 - mean_error * angle_scale)`.
4. `angle_scale` SHALL be configurable with a default of 1.0 (100° mean error → score 0).
5. IF no valid angle pairs exist, THEN AngleScore SHALL be `None`.
6. THE angle comparison SHALL be a pure function.

### Requirement 4: Motion Comparison

**User Story:** As a developer, I want to compare velocity magnitude and movement direction between player and reference.

#### Acceptance Criteria

1. THE motion comparison SHALL compute per-landmark speed similarity: `speed_sim = 1.0 - abs(p_speed - r_speed) / max(p_speed, r_speed, epsilon)` where `epsilon` is configurable (default 0.001).
2. IF both player and reference speeds are below `epsilon`, speed similarity SHALL be 1.0 (both still).
3. THE motion comparison SHALL compute per-landmark direction similarity as the dot product of unit direction vectors, clamped to [0.0, 1.0]. Opposite movement direction receives zero contribution.
4. IF a landmark's velocity is zero/near-zero (speed < epsilon), direction similarity SHALL NOT be computed for that landmark. Only speed similarity contributes.
5. THE MotionScore SHALL combine speed and direction per-landmark scores: `per_lm = speed_sim * speed_weight + direction_sim * direction_weight` (or `speed_sim` alone when direction is undefined), averaged across valid landmarks, multiplied by 100.
6. `motion_speed_weight` (default 0.5) and `motion_direction_weight` (default 0.5) SHALL be configurable.
7. THE motion comparison SHALL exclude landmarks where either player or reference motion is `None`.
8. IF no valid motion data is available, THEN MotionScore SHALL be `None`.
9. Acceleration is NOT part of the Phase 3 motion score. It is available data for future phases.
10. THE motion comparison SHALL be a pure function.

### Requirement 5: Timing Comparison

**User Story:** As a developer, I want to measure whether the player's movement occurs in the correct phase relative to the reference.

#### Acceptance Criteria

1. THE timing comparison SHALL use a movement-phase alignment metric comparing whether player and reference are in the same movement state (moving vs still) at the aligned frame.
2. A landmark is considered "moving" when its speed exceeds `motion.min_velocity_threshold` from the existing MotionConfig.
3. IF both player and reference are in the same state (both moving or both still), TimingScore SHALL receive full credit (100).
4. IF one is moving and the other is still, the penalty SHALL be proportional to the moving side's speed: `timing_score = max(0.0, 100.0 - moving_speed * timing_scale * 1000)`, bounded [0, 100].
5. `timing_scale` SHALL be configurable (default 0.5).
6. THE timing comparison SHALL be computed per-landmark and averaged across valid landmarks, producing a single frame-level TimingScore [0, 100].
7. IF no valid timing data is available, TimingScore SHALL be `None`.
8. THE timing comparison SHALL NOT implement peak detection, temporal windows, DTW, or millisecond timing offset measurement. Peak timing analysis is deferred to a future phase.
9. Timing is conceptually distinct from motion: motion measures speed/direction quality when both are moving; timing measures whether movement is occurring in the correct temporal phase.

### Requirement 6: Score Aggregation

**User Story:** As a developer, I want to combine sub-scores using configurable weights with proper handling of missing data.

#### Acceptance Criteria

1. THE aggregation SHALL use the existing `ScoringWeights` (pose=0.40, angle=0.25, motion=0.20, timing=0.15) from Phase 0 configuration. No duplication.
2. THE aggregation SHALL compute: `combined = sum(w_i * s_i) / sum(w_i)` for non-None sub-scores only (weight renormalization).
3. IF all sub-scores are None, CombinedScore SHALL be `None`.
4. CombinedScore SHALL always be in [0.0, 100.0] or None.
5. THE aggregation SHALL be deterministic and pure.

### Requirement 7: Event Rating

**User Story:** As a developer, I want to classify combined scores into PERFECT/GREAT/OK/MEH/MISS.

#### Acceptance Criteria

1. THE rating SHALL use existing `ScoringThresholds` (perfect_min=90, great_min=75, ok_min=50, meh_min=30).
2. `combined_score >= 90` → PERFECT; `>= 75` → GREAT; `>= 50` → OK; `>= 30` → MEH; else MISS.
3. IF CombinedScore is None → MISS.
4. THE rating SHALL be a pure function.

### Requirement 8: Structured Feedback

**User Story:** As a developer, I want structured, machine-readable feedback identifying what went wrong.

#### Acceptance Criteria

1. EACH FeedbackItem SHALL contain: `body_region` (string), `issue_type` (string), `severity` (float [0, 1]), `description` (measurable string).
2. Angle feedback severity: `min(1.0, angle_error_degrees / 90.0)`.
3. Pose-position feedback severity: `min(1.0, landmark_distance / 0.5)`.
4. Feedback SHALL only be emitted when the error exceeds `feedback_significance_threshold` (default 0.1).
5. `body_region` SHALL use values from the LANDMARK_REGIONS mapping (e.g., "left_arm", "right_leg", "torso").
6. `issue_type` SHALL use stable strings: "angle_mismatch", "position_off", "timing_phase_mismatch", "low_confidence".
7. Feedback SHALL NOT contain subjective statements. All descriptions SHALL be measurable.
8. Feedback is decoupled from UI — no rendering concepts in the data model.

### Requirement 9: Landmark Regions Mapping

**User Story:** As a developer, I want a stable mapping from landmark indices to body regions for structured feedback.

#### Acceptance Criteria

1. THE mapping SHALL assign each of the 33 MediaPipe landmarks to one of: "face", "left_arm", "right_arm", "torso", "left_leg", "right_leg".
2. THE mapping SHALL be deterministic and documented.
3. THE mapping SHALL be importable by scoring and feedback modules.

### Requirement 10: Missing/Invalid Data Handling

**User Story:** As a developer, I want the pipeline to handle missing data without inventing values.

#### Acceptance Criteria

1. WHEN data is None, the pipeline SHALL NOT invent substitute values.
2. Sub-scores that cannot be computed SHALL be `None`.
3. Aggregation SHALL renormalize weights over available non-None scores.
4. Feedback SHALL indicate low-confidence issues separately from movement errors.
5. The `leave_none` semantics from Phase 2 are preserved.

### Requirement 11: Configuration

**User Story:** As a developer, I want Phase 3 parameters configurable via the existing system.

#### Acceptance Criteria

1. A `[scoring.comparison]` section SHALL be added to defaults.toml with: `pose_scale_factor=200.0`, `angle_scale=1.0`, `timing_scale=0.5`, `min_valid_landmarks=8`, `feedback_significance_threshold=0.1`, `motion_speed_weight=0.5`, `motion_direction_weight=0.5`, `epsilon=0.001`.
2. Existing `[scoring.thresholds]` and `[scoring.weights]` SHALL NOT be duplicated or modified.
3. Configuration follows existing AppConfig/dataclass/loader patterns.

### Requirement 12: Determinism

**User Story:** As a developer, I want identical inputs to always produce identical outputs.

#### Acceptance Criteria

1. Same inputs + same config → identical outputs on every invocation.
2. No random, no system time, no non-deterministic operations.

### Requirement 13: Phase 3 Scope Boundaries

**User Story:** As a developer, I want explicit Phase 3 boundaries to prevent scope creep.

#### Acceptance Criteria

1. NO Practice/Arcade mode UI.
2. NO combo tracking or final grading.
3. NO DTW or temporal warping.
4. NO ML-based scoring.
5. NO music/beat synchronization.
6. NO UI rendering of scores.
7. NO modification of Phase 1/2 data models.
8. NO networking/cloud/database.
9. Full backward compatibility with Phase 1 and Phase 2.
10. NO peak timing detection or windowed timing analysis.
11. NO landmark-position interpolation between reference frames.

### Requirement 14: Testability

**User Story:** As a developer, I want Phase 3 modules testable without hardware.

#### Acceptance Criteria

1. ALL modules are pure functions testable with synthetic data.
2. Tests verify determinism, boundary scores (0, 100), missing-data, and known configurations.
3. No camera, GPU, video, or MediaPipe required.
4. Property-based tests verify score ranges [0, 100] and monotonicity.
