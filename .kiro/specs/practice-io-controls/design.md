# Design: Practice Mode I/O Controls (Camera Management + Analysis Progress)

## Overview

Add camera management (restart + device-index change) and a video-analysis
progress bar to Practice Mode. Three layers change, each minimally:

- **Camera layer** (`CameraManager`): a `restart(device_index=None)` method that
  releases resources and re-opens the camera on the given (or current) index,
  emitting the existing `state_changed` signal for status/errors.
- **Video layer** (`ReferenceAnalyzer`): an optional, additive
  `progress_callback` fired per processed sample. Backward compatible.
- **UI layer** (`PracticeWindow`): a device-index selector + "Restart camera"
  button, a camera status label, and a `QProgressBar` shown during analysis.
  `AnalysisWorker` gains a `progress(int)` Qt signal.

Plus a tiny pure helper `progress_percent(done, total)` for testable percentage
math.

No scoring/formula changes. All additive and backward compatible.

## Component 1 — CameraManager.restart / set_device_index

**File:** `src/opendance/camera/manager.py`

Currently `CameraManager.__init__(camera_config, pose_config)` bakes
`device_index` into the frozen `camera_config`, and `start()` opens that index.
`_release_resources()` already stops the worker, releases capture, closes the
detector.

Add:

```python
def restart(self, device_index: int | None = None) -> None:
    """Release the camera and re-open it (optionally on a new device index).

    Safe to call from the UI. Emits state_changed like start(). If device_index
    is given, it becomes the active index for this and future starts.
    """
    if device_index is not None:
        self._active_device_index = device_index
    self._release_resources()
    self._state = CameraState.INACTIVE  # allow start() to proceed
    self.start()
```

Change: `start()` must use `self._active_device_index` instead of reading
`self._camera_config.device_index` directly. Initialize
`self._active_device_index = camera_config.device_index` in `__init__`. The
frozen config is not mutated (immutability preserved); the manager tracks the
live index separately.

Guard against re-entrant/rapid restarts is handled by `_release_resources()`
being idempotent and `start()` early-returning when already ACTIVE (restart sets
state to INACTIVE first). Errors during open already flow through
`_set_state(CameraState.ERROR, msg)` → `state_changed`.

Add a read-only `device_index` property returning `self._active_device_index`.

No change to `state_changed`, `start`, `stop`, `pause`, `resume`, `cleanup`,
`fps`, `frame_worker` signatures.

## Component 2 — ReferenceAnalyzer progress callback

**File:** `src/opendance/video/reference_analyzer.py`

`analyze` and `_process_video` gain an optional
`progress_callback: Callable[[int, int], None] | None = None`. Inside the sample
loop:

```python
for sample_idx in range(num_samples):
    ...
    if progress_callback is not None:
        progress_callback(sample_idx + 1, num_samples)
```

- Called once per sample with (processed, total). Bounded frequency = one call
  per sample (num_samples is modest at 15 sample_fps).
- If `num_samples == 0`, optionally call `progress_callback(0, 0)` once so the UI
  can show 0/complete; keep it simple — the pure percent helper maps total 0 → 0
  (or the UI treats 0 total as "nothing to do → 100%"). We will call it once with
  (0, 0) before the loop is skipped so the bar initializes.
- Backward compatible: default None → identical behavior; existing tests
  unaffected (Requirement 5.2).

Signature change is additive (keyword-only default), so `analyze(video_path)`
still works.

## Component 3 — Pure percent helper

**File:** `src/opendance/video/progress.py` (new) or `ui/timing.py`. Prefer a new
small module in the video layer since it is analysis-progress logic.

```python
def progress_percent(done: int, total: int) -> int:
    """Integer percentage in [0, 100]. total <= 0 → 0. Clamped and non-negative."""
    if total <= 0:
        return 0
    pct = int((max(0, min(done, total)) / total) * 100)
    return max(0, min(pct, 100))
```

Pure, UI-independent, unit-testable (Requirement 5.3).

## Component 4 — AnalysisWorker progress signal

**File:** `src/opendance/ui/practice_window.py`

`AnalysisWorker` currently runs analysis and emits `finished(object)`. Add:

```python
class AnalysisWorker(QThread):
    finished = Signal(object)
    progress = Signal(int)  # 0..100

    def run(self) -> None:
        try:
            analyzer = ReferenceAnalyzer(...)
            def _cb(done: int, total: int) -> None:
                self.progress.emit(progress_percent(done, total))
            reference_seq = analyzer.analyze(self.path, progress_callback=_cb)
            analyzer.close()
            self.finished.emit(reference_seq)
        except Exception as e:
            self.finished.emit(e)
```

The callback runs on the worker thread; `self.progress.emit(...)` is a queued
signal, so the UI slot runs on the UI thread (Requirement 4.4 / 5.4).

## Component 5 — PracticeWindow UI

**File:** `src/opendance/ui/practice_window.py`

### Progress bar

- Add `self._progress_bar = QProgressBar()` (range 0..100), hidden by default.
  Placed in/near the loading overlay area or the controls column.
- On `_load_video`: show the progress bar at 0%, keep the existing loading
  overlay text ("Analyzing choreography...").
- Connect `worker.progress` → `_on_analysis_progress(int)` which sets the bar
  value.
- On `_on_analysis_finished`: set bar to 100 then hide it; on error, hide the bar
  and show the error text (existing behavior) (Requirement 4.3, 4.5).

### Camera controls

- Add a `QSpinBox` `self._device_spin` (range 0..9, value = config device index)
  and a `QPushButton` `self._restart_cam_btn` ("Restart Camera").
- `self._restart_cam_btn.clicked` → `_restart_camera()`:
  ```python
  def _restart_camera(self) -> None:
      self._reconnect_frame_signal_after_restart()  # see below
      self._camera_manager.restart(self._device_spin.value())
      self._pose_buffer.clear()  # camera change = discontinuity (Req 6.2)
  ```
- Because `restart()` creates a NEW `FrameWorker`, the window must re-connect
  `frame_ready` to `_on_camera_frame` after restart. Approach: after calling
  `restart()`, if `self._camera_manager.frame_worker is not None`, connect its
  `frame_ready` to `_on_camera_frame` (the constructor already does this on first
  start; factor the connection into a helper `_bind_frame_worker()` and call it
  from both `__init__` and after restart).
- Camera status: connect `CameraManager.state_changed` (already connected for
  error handling) to also update a small status label
  `self._camera_status_label` ("Camera: active / error / inactive").
- Briefly disable `_restart_cam_btn` while a restart is in flight to avoid spam,
  re-enable on the next `state_changed` (ACTIVE or ERROR) (Requirement 3.3).

### Frame-signal binding helper

```python
def _bind_frame_worker(self) -> None:
    fw = self._camera_manager.frame_worker
    if fw is not None:
        fw.frame_ready.connect(self._on_camera_frame)
```

Call from `__init__` (replacing the inline connect) and at the end of
`_restart_camera` (after `restart()` created the new worker).

## Data Flow

```
Camera:
  user → device spinbox + Restart button → PracticeWindow._restart_camera
       → CameraManager.restart(index) → stop+start → new FrameWorker
       → _bind_frame_worker() reconnects frame_ready → live feed resumes
       → state_changed → status label + button re-enable

Analysis:
  _load_video → AnalysisWorker.start()
       worker: analyze(path, progress_callback=cb)
              cb(done,total) → progress.emit(progress_percent(...))  [queued]
       UI: _on_analysis_progress(pct) → progress bar value
       worker.finished → _on_analysis_finished → bar=100, hide, enable playback
```

## Error Handling

- Camera open failure on restart/device-change → `state_changed(ERROR, msg)` →
  status label + error overlay; controls stay usable (Requirement 1.3, 2.3, 3.2).
- Analysis exception → `finished(Exception)` → hide bar, show error (existing
  path) (Requirement 4.5).
- `num_samples == 0` (empty/corrupt video) → analysis returns an empty sequence
  or errors as today; the progress bar initializes at 0 and the finished/error
  path handles it.

## Testing Strategy

Unit tests (pure): `progress_percent` — 0/positive/full/over/negative,
total 0 → 0, clamping, non-decreasing for increasing done.

Analyzer tests: with a mocked `cv2.VideoCapture` (as existing analyzer tests do),
`analyze(path, progress_callback=cb)` calls the callback with monotonically
non-decreasing `done` up to `total`, and the final call has `done == total`;
`analyze(path)` with no callback behaves exactly as before (reuse/extend existing
reference-analyzer tests, which already mock capture).

CameraManager tests: with a mocked capture/detector (as existing camera-manager
tests do), `restart(new_index)` releases and re-opens; `device_index` property
reflects the new index; a failed open transitions to ERROR via `state_changed`.

Offscreen PracticeWindow tests (mocked camera manager + worker): loading shows
the progress bar; `_on_analysis_progress(pct)` sets the bar; finished hides it
and enables playback; `_restart_camera` calls `CameraManager.restart` with the
spinbox value, clears the pose buffer, and re-binds the frame worker; device
spinbox default equals the configured index; status label updates on
`state_changed`.

No camera/GPU/real video; camera + analyzer + worker mocked; offscreen Qt.

## Non-Goals / Preserved

- Scoring formulas, timers, play/pause/restart, cleanup — unchanged.
- Camera resolution/config — unchanged.
- Human-readable camera names — out of scope (integer indices only).

## Traceability

| Requirement | Addressed by |
|-------------|--------------|
| 1 (restart) | `CameraManager.restart` + `_restart_camera` + `_bind_frame_worker` |
| 2 (device change) | device spinbox → `restart(index)`; `device_index` property |
| 3 (status) | `state_changed` → status label; button disable/enable |
| 4 (progress bar) | `AnalysisWorker.progress` + `_on_analysis_progress` + QProgressBar |
| 5 (testable progress) | `progress_callback` + pure `progress_percent` + Qt signal |
| 6 (integration) | preserved timers/scoring; pose buffer clear on camera change |
| 7 (config/defaults) | device index range + `camera.device_index` default |
| 8 (non-regression) | additive APIs; unchanged signatures; ruff/mypy/tests |
