# Implementation Plan: Practice Mode MVP & Real-Time Performance

## Overview

This plan implements the decoupled-rates practice loop described in the design:
real timestamps in the capture worker, a `PracticeConfig` configuration section,
split render/scoring timers in `PracticeWindow`, and restored combo/grading
semantics in `SessionTracker`. All changes are additive and preserve the public
APIs of Phase 1–3.5.

The design defines no formal "Correctness Properties" section, so testing uses
unit tests only (per the design's Testing Strategy). Test sub-tasks still honor
the project's steering rules for combo semantics and scoring/grade boundary
values. Test sub-tasks are marked optional with `*`; core implementation tasks
are not. Tests must not require a camera or GPU and use `QT_QPA_PLATFORM=offscreen`
where a widget is unavoidable.

## Tasks

- [x] 1. Add PracticeConfig configuration section
  - [x] 1.1 Add `PracticeConfig` dataclass and wire it into `AppConfig`
    - Add a frozen `PracticeConfig` dataclass in `src/opendance/config/models.py`
      with `render_fps: float = 30.0`, `scoring_fps: float = 12.0`,
      `silhouette_size: int = 250`.
    - Add a `practice_config: PracticeConfig` field to `AppConfig` using
      `field(default_factory=PracticeConfig)`.
    - Add a `[practice]` section to `src/opendance/config/defaults.toml` with the
      three default values.
    - _Requirements: 6.1, 6.5_

  - [x] 1.2 Add validation and construction for `[practice]` in the loader
    - In `src/opendance/config/loader.py`, read the merged `practice` section,
      validate `render_fps` in (1, 120], `scoring_fps` in (1, 60],
      `silhouette_size` in [50, 1000], falling back to defaults on invalid values
      (reuse `validate_value` and the existing warning pattern).
    - Construct `PracticeConfig` and pass it into the `AppConfig(...)` return.
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x]* 1.3 Write unit tests for PracticeConfig loading
    - Test defaults are applied when `[practice]` is absent.
    - Test valid overrides are respected.
    - Test invalid/out-of-range values fall back to defaults (each field).
    - _Requirements: 6.1, 6.2, 6.5_

- [x] 2. Add rate helper for interval computation
  - [x] 2.1 Implement fps-to-interval helper with clamping
    - Add a small pure helper (e.g. `fps_to_interval_ms(fps: float) -> int`
      returning `int(round(1000 / fps))`) in a suitable module such as
      `src/opendance/ui/timing.py`, with clamping to avoid zero/negative
      intervals.
    - Keep it UI-independent and side-effect free so it is unit-testable.
    - _Requirements: 1.6, 6.2, 6.4_

  - [x]* 2.2 Write unit tests for the rate helper
    - Test interval computation for representative fps values (30 → 33, 12 → 83,
      15 → 67) and clamping behavior for extreme/invalid fps.
    - _Requirements: 1.6, 6.4_

- [x] 3. Real, monotonic timestamps in FrameWorker
  - [x] 3.1 Replace fixed `+= 33` increment with real elapsed time
    - In `src/opendance/camera/frame_worker.py`, record `start = time.perf_counter()`
      at loop entry and compute `timestamp_ms = int((perf_counter() - start) * 1000)`
      for each detection.
    - Guard strict monotonicity: if a new timestamp is not greater than the
      previous one, bump it by +1 ms (MediaPipe VIDEO mode requires strictly
      increasing timestamps).
    - Keep the existing `frame_ready(frame, pose_result)` signal unchanged (no
      API change).
    - _Requirements: 3.2, 2.3, 8.2_

  - [x]* 3.2 Write unit tests for FrameWorker timestamps
    - Mock `time.perf_counter` and the capture; assert emitted timestamps are
      monotonically increasing and derived from elapsed time, not a fixed step.
    - Assert the +1 ms collision guard preserves strict monotonicity.
    - _Requirements: 3.2, 8.3, 8.5_

- [x] 4. Restore combo and grading semantics in SessionTracker
  - [x] 4.1 Fix combo branch so OK/MEH/MISS reset combo and multiplier
    - In `src/opendance/scoring/session_tracker.py`, change `update_with_rating`
      so only PERFECT and GREAT increment combo (and bump multiplier); OK, MEH,
      and MISS reset `combo = 0` and `multiplier = 1.0`.
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 4.2 Align grade bands with documented set and preserve numeric accuracy
    - Update `_calculate_grade` to produce the documented bands
      (S: ≥90, A: ≥80, B: ≥70, C: ≥60, D: ≥50, FAILED: <50), mapping the
      internal "SS"/"F" labels to the documented set (retain SS only as the
      full-combo/all-perfect internal label per `product.md`; otherwise S/FAILED).
    - Keep `accuracy_percentage` stored as a continuous numeric value.
    - _Requirements: 5.6_

  - [x]* 4.3 Write unit tests for combo semantics
    - PERFECT → combo +1; GREAT → combo +1; OK → reset; MEH → reset; MISS → reset.
    - Assert multiplier resets to 1.0 on OK/MEH/MISS.
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x]* 4.4 Write scoring/grade boundary unit tests
    - Test grade band boundaries at 100.00, 99.99, 90.00, 89.99, 80.00, 79.99,
      75.00, 74.99, 70.00, 69.99, 60.00, 59.99, 50.00, 49.99, 30.00, 29.99, 0.00.
    - Test FULL COMBO and ALL PERFECT grade labels where applicable.
    - _Requirements: 5.6_

- [x] 5. Split PracticeWindow into decoupled render and scoring timers
  - [x] 5.1 Replace the single 33 ms timer with render and scoring timers
    - In `src/opendance/ui/practice_window.py`, remove `_timer`/`_game_loop_tick`
      and add `_render_timer` (interval from `practice_config.render_fps`) and
      `_scoring_timer` (interval from `practice_config.scoring_fps`), using the
      rate helper from task 2.1.
    - Start/stop both timers together on play/pause; allow the render timer to
      keep running while paused for positioning feedback.
    - _Requirements: 1.3, 1.6, 3.3, 6.4_

  - [x] 5.2 Implement `_render_tick` (silhouette from latest pose)
    - Draw the mirrored silhouette from `self._latest_pose` using
      `get_transparent_silhouette` at `practice_config.silhouette_size`.
    - Handle empty/None pose gracefully (draw nothing/keep last, do not stall).
    - Ensure the silhouette renderer is only called from `_render_tick`.
    - _Requirements: 1.1, 1.3, 1.4, 2.4, 2.5_

  - [x] 5.3 Implement `_scoring_tick` (position-aligned scoring)
    - Score only when playing, engine ready, and pose non-empty.
    - Normalize the latest pose, `dataclasses.replace(timestamp_ms=media_player.position())`,
      call `score_frame(pose, {}, None)`, feed the rating to
      `SessionTracker.update_with_rating`, and update the scoreboard HUD.
    - Stop scoring when playback finishes and present the final result.
    - _Requirements: 3.1, 3.4, 4.4, 4.5_

  - [x] 5.4 Latest-wins pose handling and frame-copy avoidance
    - Ensure `_on_camera_frame` only overwrites `self._latest_pose` (no queue
      growth) so stale poses are dropped and full frames are not retained.
    - _Requirements: 1.2, 2.1, 2.2, 7.4_

  - [x]* 5.5 Write unit tests for timer wiring and tick guards (offscreen)
    - With `QT_QPA_PLATFORM=offscreen` and mocked camera/player, assert render
      and scoring timers are created with intervals derived from config, both
      start/stop on play/pause, and `_scoring_tick` skips when paused or pose is
      empty while `_render_tick` still runs.
    - _Requirements: 1.6, 2.5, 3.3, 6.4_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Diagnostics and stability
  - [x] 7.1 Expose effective render, inference, and scoring FPS
    - Compute render FPS and scoring FPS via rolling counters in the respective
      ticks; read inference FPS from `CameraManager.fps` / `FPSMonitor`.
    - Surface the three rates in the HUD or a small debug label.
    - _Requirements: 1.5_

  - [x] 7.2 Stop both timers on error, finish, and window close
    - On camera error and on window close, stop `_render_timer` and
      `_scoring_timer`, release the media player, and terminate the analysis
      worker (extend existing `closeEvent`/error paths).
    - _Requirements: 7.1, 7.2, 7.3_

  - [x]* 7.3 Write unit tests for cleanup and error handling (offscreen)
    - Assert `closeEvent` stops both timers, stops the player, and terminates a
      running worker; assert camera-error path stops timers safely.
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 8. Integration and non-regression verification
  - [x]* 8.1 Write an offscreen integration test for the scoring path
    - With mocked camera/player and a small synthetic reference sequence, drive
      a few `_scoring_tick` calls and assert HUD values (grade, accuracy, combo)
      update using `media_player.position()` alignment.
    - _Requirements: 3.1, 4.4, 4.5_

  - [x]* 8.2 Confirm non-regression of existing suites
    - Run the full test suite plus ruff and mypy; ensure no new failures or
      type/lint errors and that Phase 1–3.5 public APIs are unchanged.
    - _Requirements: 8.1, 8.2, 8.4, 8.5_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test tasks and can be skipped for a faster
  MVP, but the steering "definition of done" expects combo, boundary, and config
  tests to exist before the feature is considered complete.
- Each task references specific requirement sub-clauses for traceability.
- The design defines no formal Correctness Properties, so no property-based test
  tasks are included; unit tests cover combo semantics and scoring/grade
  boundaries per the testing steering file.
- All tests avoid real hardware; camera and MediaPipe are mocked and Qt widgets
  run under `QT_QPA_PLATFORM=offscreen`.
- Checkpoints ensure incremental validation with `pytest`, `ruff`, and `mypy`.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "3.1", "4.1"] },
    { "id": 1, "tasks": ["1.2", "2.2", "3.2", "4.2"] },
    { "id": 2, "tasks": ["1.3", "4.3", "4.4", "5.1"] },
    { "id": 3, "tasks": ["5.2", "5.3", "5.4"] },
    { "id": 4, "tasks": ["5.5", "7.1", "7.2"] },
    { "id": 5, "tasks": ["7.3", "8.1"] },
    { "id": 6, "tasks": ["8.2"] }
  ]
}
```
