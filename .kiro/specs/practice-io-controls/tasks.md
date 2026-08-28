# Implementation Plan: Practice Mode I/O Controls (Camera + Analysis Progress)

## Overview

Add camera restart/device-change (camera layer), an additive analysis progress
callback (video layer), a pure percent helper, an `AnalysisWorker.progress`
signal, and PracticeWindow UI (device selector, restart button, camera status,
progress bar). All additive and backward compatible; no scoring changes.

Unit + offscreen widget tests (design defines no formal correctness properties).
Optional test tasks are marked `*`.

## Tasks

- [x] 1. Pure analysis-progress percent helper
  - [x] 1.1 Implement `progress_percent(done, total)`
    - Add `src/opendance/video/progress.py` with a pure
      `progress_percent(done: int, total: int) -> int` returning an int in
      [0, 100]; total <= 0 → 0; clamp done into [0, total].
    - _Requirements: 5.3_

  - [x]* 1.2 Unit tests for `progress_percent`
    - total 0 → 0; done 0 → 0; done == total → 100; done > total → 100;
      negative done → 0; midpoint; non-decreasing for increasing done.
    - _Requirements: 5.3_

- [x] 2. ReferenceAnalyzer progress callback
  - [x] 2.1 Add optional `progress_callback` to `analyze`/`_process_video`
    - Add keyword param `progress_callback: Callable[[int, int], None] | None =
      None`. Call it once with `(0, 0)` before the loop when `num_samples == 0`,
      and with `(sample_idx + 1, num_samples)` after each processed sample.
      Default None → unchanged behavior.
    - _Requirements: 4.6, 5.1, 5.2_

  - [x]* 2.2 Analyzer progress tests (mocked capture)
    - With a mocked `cv2.VideoCapture`, assert the callback is called with
      non-decreasing `done` up to `total`, final call `done == total`; and that
      `analyze(path)` without a callback still returns the same sequence
      (backward compatible).
    - _Requirements: 5.1, 5.2_

- [x] 3. CameraManager restart / device change
  - [x] 3.1 Add `restart` + `device_index` and use an active index in `start`
    - Track `self._active_device_index = camera_config.device_index` in
      `__init__`; make `start()` open `self._active_device_index`. Add
      `restart(device_index: int | None = None)` that sets the active index (if
      given), releases resources, resets state to INACTIVE, and calls `start()`.
      Add a read-only `device_index` property. Preserve `state_changed`, cleanup,
      and all existing signatures.
    - _Requirements: 1.1, 1.4, 2.1, 2.2, 2.5_

  - [x]* 3.2 CameraManager restart tests (mocked capture/detector)
    - `restart(new_index)` releases then re-opens; `device_index` reflects the
      new index; failed open → ERROR via `state_changed`; restart with no arg
      reuses the current index.
    - _Requirements: 1.1, 1.3, 2.1, 2.3_

- [x] 4. AnalysisWorker progress signal
  - [x] 4.1 Add `progress` signal and wire the callback
    - In `practice_window.py`, add `progress = Signal(int)` to `AnalysisWorker`;
      in `run`, pass a callback to `analyze` that emits
      `progress_percent(done, total)`. Keep `finished(object)` behavior.
    - _Requirements: 4.4, 5.4_

- [ ] 5. PracticeWindow: progress bar
  - [ ] 5.1 Add and wire the QProgressBar
    - Add `self._progress_bar` (0..100), hidden by default. On `_load_video`
      show it at 0%. Connect `worker.progress` → `_on_analysis_progress(int)`
      (set value). On `_on_analysis_finished` set 100 then hide; on error hide
      and show the error text (existing path).
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 6.1_

- [ ] 6. PracticeWindow: camera controls
  - [ ] 6.1 Device selector, restart button, status, frame re-binding
    - Add `self._device_spin` (QSpinBox 0..9, default = config device index),
      `self._restart_cam_btn`, and `self._camera_status_label`. Factor frame-
      worker connection into `_bind_frame_worker()` (call from `__init__` and
      after restart). Implement `_restart_camera()` → `restart(spin value)`,
      clear `_pose_buffer`, re-bind frame worker. Update status label + toggle
      the restart button on `state_changed` (disable during restart, re-enable on
      ACTIVE/ERROR).
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 6.2, 6.3_

- [ ] 7. Checkpoint - tests pass
  - Run suite + ruff + mypy; confirm no regressions.

- [ ]* 8. Offscreen widget tests for I/O controls
  - Extend `tests/unit/test_practice_window.py` (mocked camera manager + worker):
    loading shows progress bar; `_on_analysis_progress(pct)` sets bar value;
    finished hides bar + enables playback; `_restart_camera` calls
    `CameraManager.restart` with the spinbox value, clears `_pose_buffer`, and
    re-binds the frame worker; device spinbox default equals configured index;
    status label updates on `state_changed`.
  - _Requirements: 1.1, 2.1, 3.1, 4.1, 4.3, 6.2_

- [ ] 9. Final checkpoint and docs
  - Full suite + ruff + mypy green. Update `docs/development-status.md` (Phase 4
    sub-specs) to record camera management + analysis progress bar.
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

## Notes

- `*` tasks are optional tests; core tasks are not.
- Analyzer/camera/worker mocked in tests; offscreen Qt; no real hardware/video.
- Camera layer owns lifecycle; UI never touches OpenCV directly.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "3.1"] },
    { "id": 1, "tasks": ["1.2", "2.2", "3.2", "4.1"] },
    { "id": 2, "tasks": ["5.1"] },
    { "id": 3, "tasks": ["6.1"] },
    { "id": 4, "tasks": ["7"] },
    { "id": 5, "tasks": ["8"] },
    { "id": 6, "tasks": ["9"] }
  ]
}
```
