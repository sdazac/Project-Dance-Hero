# Design: Complete Live Scoring (Angles + Motion)

## Overview

Feed real player joint angles and motion features into the live scoring path so
all four similarity metrics (pose, angle, motion, timing) contribute during
practice. The change is confined to `PracticeWindow._scoring_tick` plus a small,
pure, unit-testable helper for deriving current-frame motion from a short rolling
buffer of recent poses. No scoring formula, engine API, or reference pipeline
changes.

## Current State

```python
# practice_window.py _scoring_tick (today)
norm_pose = normalize_pose(self._latest_pose, cfg)
norm_pose = dataclasses.replace(norm_pose, timestamp_ms=media_player.position())
comparison = self._scoring_engine.score_frame(norm_pose, {}, None)   # <- {} and None
```

`ScoringEngine.score_frame(player_pose, player_angles, player_motion)` already
handles empty angles / None motion gracefully (skips those sub-scores, and
`aggregate_scores` renormalizes over present metrics). So filling in the two
missing arguments is a safe, additive completion.

## Key Constraint: motion needs a sequence

`compute_sequence_motion(poses, config)` derives velocity via differences between
consecutive frames (needs ≥2 timestamped poses). Live scoring only has the
current frame, so we keep a **bounded rolling buffer** of recent normalized poses
(with playback-position timestamps) and compute motion for the current frame from
that buffer.

Reusing `compute_sequence_motion` verbatim (rather than writing new motion math)
guarantees the live motion matches the reference motion formula exactly.

## Components and Changes

### 1. New pure helper: current-frame motion from a buffer

**File:** `src/opendance/motion/live_motion.py` (new)

```python
from collections import deque

def motion_for_latest(
    pose_buffer: Sequence[NormalizedPose],
    config: MotionConfig,
) -> MotionFeatures | None:
    """Compute MotionFeatures for the most recent pose in the buffer.

    Runs compute_sequence_motion over the buffered poses (ordered oldest→newest)
    and returns the motion features for the LAST (current) pose. Returns None if
    fewer than 2 valid poses are available (velocity is undefined).
    """
    if len(pose_buffer) < 2:
        return None
    results = compute_sequence_motion(list(pose_buffer), config)
    return results[-1] if results else None
```

Notes:
- Pure, UI-independent, no Qt/camera. Directly unit-testable (Requirement 6).
- For the last element, `compute_sequence_motion` uses a **backward difference**
  (frames N-2, N-1), which is exactly the correct "velocity up to now" for live
  play.
- Buffer is ordered oldest→newest.

### 2. PracticeWindow: maintain the buffer and pass angles + motion

**File:** `src/opendance/ui/practice_window.py`

State additions in `__init__`:

```python
from collections import deque
# Rolling buffer of recent normalized player poses for live motion. Bounded so
# memory does not accumulate (practice-mode-mvp Req 7.4). 5 frames is enough for
# a stable backward-difference velocity at scoring_fps.
self._pose_buffer: deque[NormalizedPose] = deque(maxlen=5)
```

Revised `_scoring_tick` (only the scoring branch changes):

```python
def _scoring_tick(self):
    # ... fps bookkeeping ...
    if not self._is_playing or not self._scoring_engine or not self._latest_pose:
        return
    if self._latest_pose.is_empty:
        return

    norm_pose = normalize_pose(self._latest_pose, self._app_config.normalization_config)
    if not norm_pose.valid:
        return

    position_ms = self._media_player.position()
    norm_pose = dataclasses.replace(norm_pose, timestamp_ms=position_ms)

    # Buffer the aligned pose for live motion (bounded, latest-wins).
    self._pose_buffer.append(norm_pose)

    # Live angles (single-frame) and motion (from the rolling buffer).
    player_angles = compute_joint_angles(norm_pose)
    player_motion = motion_for_latest(self._pose_buffer, self._app_config.motion_config)

    comparison = self._scoring_engine.score_frame(norm_pose, player_angles, player_motion)
    if comparison:
        self._session.update_with_rating(comparison.event_rating)
        self._scoreboard.update_score(
            self._session.state.current_grade,
            self._session.state.accuracy_percentage,
            self._session.state.combo,
        )
```

Buffer reset:
- Clear `self._pose_buffer` in `_restart_video()` so a new session starts with a
  clean motion history.

Timestamp monotonicity in the buffer:
- Player poses are stamped with `media_player.position()`. During normal forward
  playback these increase. If two consecutive scoring ticks read the same
  position (paused edge, or scoring faster than the player clock advances), the
  motion helper must not divide by zero. `compute_sequence_motion` already
  returns dt=0 → None-motion for equal timestamps, so this is safe. As defensive
  polish, the helper may skip appending a duplicate-timestamp pose, but relying
  on the existing dt≤0 guard is sufficient and keeps the change minimal.

### 3. No changes to engine, angles, motion, or reference

- `ScoringEngine.score_frame` already accepts and correctly uses non-empty
  angles and a real `MotionFeatures`.
- `compute_joint_angles` and `compute_sequence_motion` are reused unchanged.

## Data Flow (revised scoring path)

```
latest raw pose (camera) ──► normalize_pose ──► valid? ──► stamp timestamp = position()
                                                                │
                                              append to rolling pose buffer (maxlen=5)
                                                                │
                        ┌───────────────────────────────────────┴───────────────┐
                        ▼                                                         ▼
             compute_joint_angles(pose)                       motion_for_latest(buffer, cfg)
                        │                                                         │
                        └───────────────► score_frame(pose, angles, motion) ◄─────┘
                                                    │
                                    pose + angle + motion + timing → aggregate
                                                    │
                                          rating → SessionTracker → HUD
```

## Error Handling

- Empty/invalid pose → tick returns early (unchanged guard).
- < 2 buffered poses → `motion_for_latest` returns None; scoring proceeds with
  pose + angle (+ timing None). No crash.
- Duplicate/backward timestamps → dt≤0 handled inside `compute_sequence_motion`
  (None-motion), no division by zero.

## Testing Strategy

Unit tests (pure, no Qt/camera):

1. **`motion_for_latest` helper** (`tests/unit/test_live_motion.py`):
   - < 2 poses → None.
   - 2 poses with known displacement and dt → expected speed/velocity for the
     latest frame (matches `compute_sequence_motion` backward-difference).
   - equal timestamps → None-motion (dt=0) without error.
   - buffer of N poses → returns motion for the last pose.

2. **PracticeWindow live scoring wiring** (extend
   `tests/unit/test_practice_window.py`, offscreen, mocked player/camera):
   - `_scoring_tick` calls `score_frame` with a NON-empty angles dict and (after
     ≥2 ticks) a non-None motion argument (spy on a fake engine capturing args).
   - buffer is bounded (does not exceed maxlen) and is cleared on `_restart_video`.
   - first tick (single pose) passes motion=None; second tick passes motion.

3. **Integration** (extend
   `tests/integration/test_practice_scoring_path.py`, offscreen): driving a few
   ticks with a real ScoringEngine and a synthetic reference that HAS angle and
   motion data yields a `FrameComparison` whose `angle_score` and `motion_score`
   are non-None, proving all four metrics are live.

No hardware required; camera/player mocked, poses synthetic.

## Non-Goals / Preserved

- Scoring formulas, weights, thresholds — unchanged.
- `ScoringEngine`, `compute_joint_angles`, `compute_sequence_motion` signatures —
  unchanged.
- Reference analysis pipeline — unchanged.

## Traceability

| Requirement | Addressed by |
|-------------|--------------|
| 1 (live angles) | `compute_joint_angles` in `_scoring_tick` |
| 2 (live motion) | rolling buffer + `motion_for_latest` |
| 3 (timestamps/alignment) | position() stamp retained; dt from timestamps |
| 4 (weights/config) | existing weights + MotionConfig reused |
| 5 (performance) | scoring-tick only; single-frame + buffer step |
| 6 (testable helper) | pure `motion_for_latest` + unit tests |
| 7 (non-regression) | unchanged APIs, ruff/mypy, existing tests |
