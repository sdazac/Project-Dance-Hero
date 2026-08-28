# Implementation Plan: Practice Mode Playback Controls (Seek + Speed)

## Overview

Add a seek slider and a configurable playback-speed selector to `PracticeWindow`,
wired to the existing `QMediaPlayer`, preserving position-based scoring alignment.
Config gains a validated speed list. A pure slider↔ms helper keeps the mapping
unit-testable. All additive and backward compatible.

Unit + offscreen widget tests (design defines no formal correctness properties).
Optional test tasks are marked `*`.

## Tasks

- [x] 1. Configuration: playback speeds
  - [x] 1.1 Add speed fields to `PracticeConfig` + defaults.toml
    - Add `playback_speeds: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5)` and
      `default_playback_speed: float = 1.0` to `PracticeConfig`.
    - Add `playback_speeds` and `default_playback_speed` to the `[practice]`
      section of `defaults.toml`.
    - _Requirements: 5.1, 5.3, 6.2_

  - [x] 1.2 Validate `[practice]` speeds in the loader
    - Parse `playback_speeds` as a list of floats; keep values in [0.25, 4.0];
      empty → default tuple. Validate `default_playback_speed` in [0.25, 4.0] and
      ensure it is in the validated list (else 1.0 if present, else first speed).
      Convert to tuple. Reuse `validate_value`/warning pattern.
    - _Requirements: 5.2, 5.4, 5.5_

  - [ ]* 1.3 Config unit tests
    - defaults; valid list override; invalid entries filtered; empty→default;
      default-not-in-list fallback; out-of-range default fallback.
    - _Requirements: 5.1, 5.2, 5.3_

- [x] 2. Pure slider↔ms mapping helpers
  - [x] 2.1 Implement `slider_to_ms` and `ms_to_slider`
    - Add to `src/opendance/ui/timing.py`: pure conversions with clamping and
      zero-duration / zero-max guards (return 0).
    - _Requirements: 4.1_

  - [x]* 2.2 Unit tests for the mapping helpers
    - endpoints (0, max), midpoint, out-of-range clamp, zero-duration/zero-max
      guard, approximate round-trip.
    - _Requirements: 4.1_

- [ ] 3. Seek control in PracticeWindow
  - [ ] 3.1 Add the seek slider and wire media signals
    - Add `self._seek_slider` (QSlider horizontal, range 0..1000), and
      `self._user_seeking = False`. Connect `positionChanged` (update slider when
      not seeking, using `ms_to_slider`) and `durationChanged` (store duration,
      enable slider when > 0). Slider disabled until ready.
    - _Requirements: 1.1, 1.2, 1.6, 3.3_

  - [ ] 3.2 Implement seek + buffer clear
    - `sliderPressed` → `_user_seeking = True`; `sliderReleased` → compute ms via
      `slider_to_ms`, call `_seek_to(ms)`, `_user_seeking = False`.
    - `_seek_to(position_ms)`: `setPosition(ms)` then `self._pose_buffer.clear()`.
    - _Requirements: 1.3, 1.4, 1.5_

- [ ] 4. Speed control in PracticeWindow
  - [ ] 4.1 Add the speed selector and apply rate
    - Add `self._speed_combo` (QComboBox) populated from
      `practice_config.playback_speeds` with labels like "1.0x"; select the
      configured default. Disabled until ready. On change →
      `_set_playback_speed(rate)` calling `setPlaybackRate(rate)`.
    - Apply `default_playback_speed` to the player when the source becomes ready
      (`_on_analysis_finished`). `_restart_video` preserves the selected speed
      and clears the pose buffer (buffer clear already present; keep it).
    - Enable slider + combo in `_on_analysis_finished` alongside play/restart.
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3_

- [ ] 5. Checkpoint - tests pass
  - Run suite + ruff + mypy; confirm no regressions.

- [ ]* 6. Offscreen widget tests for controls
  - Extend `tests/unit/test_practice_window.py` (mocked media player): slider
    disabled before ready / enabled after `_on_analysis_finished`;
    `durationChanged` enables + stores duration; `positionChanged` updates slider
    when not seeking and NOT while `_user_seeking`; slider release calls
    `setPosition(mapped_ms)` and clears `_pose_buffer`; speed combo change calls
    `setPlaybackRate(rate)`; `_restart_video` preserves selected speed and clears
    buffer.
  - _Requirements: 1.2, 1.3, 1.5, 2.2, 3.2, 4.3_

- [ ] 7. Final checkpoint
  - Full suite + ruff + mypy green. Confirm APIs backward compatible.
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

## Notes

- `*` tasks are optional tests; core tasks are not.
- TOML has no tuple; loader reads a list and converts to tuple.
- Offscreen Qt tests with a mocked QMediaPlayer; no camera/GPU/real video.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["1.2", "2.2"] },
    { "id": 2, "tasks": ["1.3", "3.1"] },
    { "id": 3, "tasks": ["3.2", "4.1"] },
    { "id": 4, "tasks": ["5"] },
    { "id": 5, "tasks": ["6"] },
    { "id": 6, "tasks": ["7"] }
  ]
}
```
