# Requirements: Complete Live Scoring (Angles + Motion)

## Introduction

The real-time practice loop currently scores the player using pose similarity
only. In `PracticeWindow._scoring_tick`, the call is
`score_frame(norm_pose, {}, None)` — the joint-angle dictionary is empty and the
motion features are `None`. As a result, two of the four configured similarity
dimensions (angle 25%, motion 20%) are inert during live play, and the aggregate
score is renormalized over pose (40%) + timing (15%) only.

This is a correctness/completeness gap: `product.md`, `ai-ml.md`, and
`architecture.md` all specify four independent similarity metrics (pose, angle,
motion, timing) with configurable weights, and the reference video is already
analyzed with angles and motion. This spec feeds real player joint angles and
motion features into the live scoring path so all four metrics contribute, as
designed.

This is an additive enhancement. It does not change any scoring formula, the
`ScoringEngine` API, or the reference analysis pipeline.

## Glossary

- **Player angles**: `dict[str, float | None]` of signed joint angles computed
  from the current normalized player pose via `compute_joint_angles`.
- **Player motion**: `MotionFeatures | None` for the current frame, derived from
  a short rolling buffer of recent normalized player poses.
- **Pose buffer**: a small bounded, ordered collection of the most recent valid
  normalized player poses used to compute motion (velocity needs ≥2 frames).
- **Scoring tick**: the `_scoring_tick` invocation running at `scoring_fps`.

## Requirements

### Requirement 1 — Live joint angles feed the angle score

**User Story:** As a user, I want my joint angles compared to the reference, so
my score reflects limb positioning, not just landmark distance.

#### Acceptance Criteria

1. WHEN a valid player pose is scored THEN the system SHALL compute player joint
   angles from the normalized pose using the existing `compute_joint_angles`.
2. WHEN player angles are computed THEN the system SHALL pass them to
   `ScoringEngine.score_frame` in place of the current empty dict.
3. WHEN the reference frame has angle data AND player angles are present THEN the
   resulting `FrameComparison.angle_score` SHALL be non-None.
4. WHEN the player pose is empty or invalid THEN the system SHALL NOT attempt to
   compute angles and SHALL skip scoring for that tick (existing guard behavior
   preserved).

### Requirement 2 — Live motion features feed the motion and timing scores

**User Story:** As a user, I want my movement speed and direction compared to the
reference, so my score reflects dynamics and timing.

#### Acceptance Criteria

1. WHEN valid player poses arrive over time THEN the system SHALL maintain a
   bounded rolling buffer of the most recent normalized player poses.
2. WHEN at least two timestamped valid poses are buffered THEN the system SHALL
   compute motion features for the current frame using the existing motion
   computation, with velocity derived from real elapsed time between frames.
3. WHEN motion features are available THEN the system SHALL pass them to
   `ScoringEngine.score_frame` in place of the current `None`.
4. WHEN fewer than two valid poses are available (session start) THEN the system
   SHALL pass `None` for motion and still score pose/angle (no crash, no stall).
5. WHEN the buffer grows THEN it SHALL be bounded to a small fixed size so memory
   does not accumulate (Requirement 7.4 of practice-mode-mvp).

### Requirement 3 — Timestamps and alignment remain correct

**User Story:** As a user, I want scoring to stay aligned to the real playback
position after this change.

#### Acceptance Criteria

1. WHEN a frame is scored THEN the player pose timestamp SHALL still be set to
   `media_player.position()` (existing behavior) before calling `score_frame`.
2. WHEN motion is computed from buffered poses THEN velocity SHALL use the real
   inter-frame elapsed time (timestamps), consistent with the reference motion
   computation.
3. WHEN the aligned reference frame lacks angle or motion data THEN the affected
   sub-score SHALL be None and the aggregate SHALL renormalize over the available
   metrics (existing engine behavior, unchanged).

### Requirement 4 — Weights and configuration honored

**User Story:** As a user on varied hardware, I want scoring weights to work as
configured now that all four metrics are live.

#### Acceptance Criteria

1. WHEN all four sub-scores are present THEN the aggregate SHALL combine them
   using the configured `ScoringWeights` (default pose .40 / angle .25 /
   motion .20 / timing .15), unchanged.
2. WHEN motion is computed THEN it SHALL use `MotionConfig` (e.g.
   `min_velocity_threshold`) from `AppConfig`, unchanged.
3. WHEN this feature is added THEN no new hardcoded scoring constants SHALL be
   introduced (reuse existing config).

### Requirement 5 — Performance and non-blocking behavior

**User Story:** As a user, I want live full scoring to stay smooth.

#### Acceptance Criteria

1. WHEN full scoring runs THEN it SHALL run only at `scoring_fps` (in
   `_scoring_tick`), not in the render tick.
2. WHEN angles and motion are computed THEN the per-tick cost SHALL remain small
   (single-frame angle computation + single-step motion from the buffer), and
   SHALL NOT block the UI thread noticeably.
3. WHEN the render loop runs THEN its smoothness SHALL be unaffected (angles and
   motion are not computed in `_render_tick`).

### Requirement 6 — Correctness helper is independently testable

**User Story:** As a maintainer, I want the live-motion helper unit-tested.

#### Acceptance Criteria

1. WHEN motion for the current frame is derived from the buffer THEN the logic
   SHALL live in a pure, UI-independent helper (or reuse the existing motion
   function) that can be unit-tested without Qt or a camera.
2. WHEN two poses with a known time delta and known displacement are provided
   THEN the helper SHALL produce the expected velocity/speed (matching the
   existing motion formula), and SHALL return None-motion when only one pose is
   available.

### Requirement 7 — Non-regression

**User Story:** As a maintainer, I want existing behavior and APIs preserved.

#### Acceptance Criteria

1. WHEN this work is complete THEN all existing tests SHALL pass.
2. WHEN inspected THEN `ScoringEngine.score_frame` / `score_sequence`,
   `compute_joint_angles`, and `compute_sequence_motion` signatures SHALL be
   unchanged.
3. WHEN ruff and mypy run THEN they SHALL report no new errors.
4. WHEN tests run THEN they SHALL NOT require a camera or GPU.

## Out of Scope

- Changing any scoring formula, weights defaults, or thresholds.
- Changing the reference analysis pipeline.
- Acceleration-based live scoring (motion_compare already excludes acceleration).
- Analytics/weak-section detection (separate spec).
