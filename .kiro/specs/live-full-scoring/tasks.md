# Implementation Plan: Complete Live Scoring (Angles + Motion)

## Overview

Feed real player joint angles and motion features into `PracticeWindow._scoring_tick`
so all four similarity metrics contribute during live play. Add a small pure
helper `motion_for_latest` that reuses the existing `compute_sequence_motion` over
a bounded rolling pose buffer. No scoring formula, engine API, or reference
pipeline changes.

Testing uses unit + integration tests (the design defines no formal correctness
properties beyond the existing motion formula, so no new PBT tasks). Optional
test tasks are marked `*`.

## Tasks

- [x] 1. Add the pure current-frame motion helper
  - [x] 1.1 Implement `motion_for_latest`
    - Create `src/opendance/motion/live_motion.py` with
      `motion_for_latest(pose_buffer, config: MotionConfig) -> MotionFeatures | None`.
    - Return None if fewer than 2 poses; otherwise run
      `compute_sequence_motion(list(pose_buffer), config)` and return the last
      element. Keep it pure and UI-independent.
    - _Requirements: 2.2, 2.4, 6.1, 6.2_

  - [x]* 1.2 Unit tests for `motion_for_latest`
    - < 2 poses → None; 2 poses with known displacement/dt → expected
      speed/velocity for the latest frame; equal timestamps → None-motion (dt=0)
      without error; N-pose buffer → motion for the last pose.
    - Place in `tests/unit/test_live_motion.py`.
    - _Requirements: 6.2_

- [x] 2. Wire angles + motion into the live scoring tick
  - [x] 2.1 Maintain a bounded rolling pose buffer
    - In `src/opendance/ui/practice_window.py`, add
      `self._pose_buffer: deque[NormalizedPose] = deque(maxlen=5)` in `__init__`.
    - Append the timestamp-aligned normalized pose in `_scoring_tick` before
      scoring; clear the buffer in `_restart_video`.
    - _Requirements: 2.1, 2.5, 3.1_

  - [x] 2.2 Compute and pass player angles and motion to `score_frame`
    - In `_scoring_tick`, compute `player_angles = compute_joint_angles(norm_pose)`
      and `player_motion = motion_for_latest(self._pose_buffer, motion_config)`,
      then call `score_frame(norm_pose, player_angles, player_motion)`.
    - Preserve all existing guards (playing, engine ready, non-empty, valid) and
      the `media_player.position()` timestamp alignment.
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.3, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3_

  - [x]* 2.3 Unit tests for live scoring wiring (offscreen)
    - Extend `tests/unit/test_practice_window.py`: `_scoring_tick` passes a
      non-empty angles dict; after ≥2 ticks passes non-None motion; first tick
      passes motion=None; buffer is bounded and cleared on `_restart_video`.
    - Use a fake engine capturing `score_frame` args; mock camera/player.
    - _Requirements: 1.2, 2.3, 2.4, 2.5_

- [x] 3. Checkpoint - tests pass
  - Run the suite + ruff + mypy; confirm no regressions.

- [x]* 4. Integration test: all four metrics live
  - Extend `tests/integration/test_practice_scoring_path.py`: with a real
    ScoringEngine and a synthetic reference that has angle AND motion data,
    drive a few ticks and assert the resulting `FrameComparison.angle_score` and
    `motion_score` are non-None (proving angle/motion now contribute live).
  - _Requirements: 1.3, 2.3_

- [x] 5. Final checkpoint and status update
  - Run full suite + ruff + mypy. Update `docs/development-status.md` to note the
    Phase 4 scoring inputs limitation is resolved (live angles + motion now fed).
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

## Notes

- `*` tasks are optional tests; core wiring tasks are not optional.
- Reuses `compute_sequence_motion` and `compute_joint_angles` unchanged.
- No hardware in tests; camera/player mocked, poses synthetic, offscreen Qt.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["2.3", "3"] },
    { "id": 4, "tasks": ["4"] },
    { "id": 5, "tasks": ["5"] }
  ]
}
```
