# Implementation Plan: Camera Capture & Real-Time Pose Detection Pipeline (Phase 1)

## Overview

This plan implements Phase 1 of OpenDance AI — camera capture, real-time pose detection via MediaPipe, and skeleton visualization in the PySide6 UI. Tasks are ordered by dependency: configuration extensions first, then data models, then components, then UI integration. All tests use mocked/synthetic inputs (no camera or GPU hardware required in CI).

## Tasks

- [ ] 1. Extend configuration system for camera and pose settings
  - [x] 1.1 Add CameraConfig and PoseConfig dataclasses to models.py
    - Add `CameraConfig` frozen dataclass with fields: `device_index: int = 0`, `resolution_width: int = 640`, `resolution_height: int = 480`, `consecutive_failure_threshold: int = 10`
    - Add `PoseConfig` frozen dataclass with fields: `model_path: str = "assets/models/pose_landmarker.task"`, `skeleton_visibility_threshold: float = 0.5`
    - Extend `AppConfig` with `camera_config: CameraConfig` and `pose_config: PoseConfig` fields using `field(default_factory=...)`
    - Update `__all__` export in `src/opendance/config/__init__.py` to include `CameraConfig`, `PoseConfig`
    - **Files:** `src/opendance/config/models.py`, `src/opendance/config/__init__.py`
    - _Requirements: 15.3_

  - [x] 1.2 Extend defaults.toml with [camera] and [pose] sections
    - Append `[camera]` section with `device_index = 0`, `resolution_width = 640`, `resolution_height = 480`, `consecutive_failure_threshold = 10`
    - Append `[pose]` section with `model_path = "assets/models/pose_landmarker.task"`, `skeleton_visibility_threshold = 0.5`
    - **Files:** `src/opendance/config/defaults.toml`
    - _Requirements: 15.1, 15.2_

  - [x] 1.3 Extend loader.py to validate and build CameraConfig and PoseConfig
    - Add validation ranges: `device_index >= 0`, `resolution_width > 0`, `resolution_height > 0`, `consecutive_failure_threshold >= 1`, `skeleton_visibility_threshold` in [0.0, 1.0], `model_path` non-empty string
    - Extend `_build_config()` to parse `[camera]` and `[pose]` TOML sections into `CameraConfig` and `PoseConfig`
    - Invalid values fall back to defaults with a logged warning (same pattern as scoring config)
    - **Files:** `src/opendance/config/loader.py`
    - _Requirements: 15.4, 15.5_

  - [x] 1.4 Add hypothesis to dev dependencies in pyproject.toml
    - Add `"hypothesis>=6.0"` to `[project.optional-dependencies] dev` list
    - **Files:** `pyproject.toml`
    - _Requirements: 16.3, 16.4_

  - [ ]* 1.5 Write property tests for camera/pose configuration validation and merge
    - **Property 12: Camera and pose configuration validation and merge**
    - Test that invalid types/ranges fall back to defaults
    - Test that partial TOML overrides merge correctly (unspecified keys retain defaults)
    - Test round-trip: load defaults → build config → values match declared defaults
    - **Validates: Requirements 15.4, 15.5**
    - **Files:** `tests/unit/test_config_camera_pose.py`

- [ ] 2. Implement CameraState enum and FPS monitor
  - [x] 2.1 Create CameraState enum
    - Create `src/opendance/camera/state.py` with `CameraState` enum: `INACTIVE`, `ACTIVE`, `PAUSED`, `ERROR` (using `auto()`)
    - Update `src/opendance/camera/__init__.py` to export `CameraState`
    - **Files:** `src/opendance/camera/state.py`, `src/opendance/camera/__init__.py`
    - _Requirements: 3.1_

  - [x] 2.2 Implement FPSMonitor class
    - Create `src/opendance/camera/fps_monitor.py` with `FPSMonitor` class
    - Use `collections.deque(maxlen=window_size)` with default `window_size=30`
    - Implement `tick()` recording `time.perf_counter()`, `fps` property calculating `(count - 1) / elapsed`, `reset()` clearing timestamps
    - Return 0.0 when fewer than 2 timestamps exist
    - Update `src/opendance/camera/__init__.py` to export `FPSMonitor`
    - **Files:** `src/opendance/camera/fps_monitor.py`, `src/opendance/camera/__init__.py`
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x]* 2.3 Write property tests for FPSMonitor
    - **Property 8: FPS rolling window reflects recent frame rate**
    - Generate monotonically increasing timestamp sequences via hypothesis
    - Verify `fps == (window_count - 1) / (newest - oldest)` for any valid sequence
    - Verify reset clears state, fps returns 0.0 after reset
    - **Validates: Requirements 4.1, 4.3**
    - **Files:** `tests/unit/test_fps_monitor.py`

- [ ] 3. Implement pose result data models
  - [x] 3.1 Create Landmark, WorldLandmark, and PoseResult dataclasses
    - Create `src/opendance/pose/result.py` with frozen dataclasses: `Landmark(x, y, z, visibility, presence)`, `WorldLandmark(x, y, z, visibility, presence)`, `PoseResult(landmarks: tuple[Landmark, ...], world_landmarks: tuple[WorldLandmark, ...], timestamp_ms: int)`
    - Implement `PoseResult.is_empty` property and `PoseResult.empty()` static factory
    - Update `src/opendance/pose/__init__.py` to export `PoseResult`, `Landmark`, `WorldLandmark`
    - **Files:** `src/opendance/pose/result.py`, `src/opendance/pose/__init__.py`
    - _Requirements: 7.5, 7.6, 7.7, 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 3.2 Write property tests for PoseResult structural completeness
    - **Property 5: PoseResult structural completeness**
    - Generate random landmarks via hypothesis strategies (floats in [0.0, 1.0] for coords/visibility/presence)
    - Verify exactly 33 landmarks when constructed with 33, empty when constructed with ()
    - Verify immutability (frozen dataclass), tuple type
    - Verify `is_empty` is True iff `landmarks == ()`
    - **Validates: Requirements 7.5, 7.6, 7.7, 8.1, 8.2, 8.4, 8.5**
    - **Files:** `tests/unit/test_pose_result.py`

- [ ] 4. Implement PoseDetector (MediaPipe wrapper)
  - [x] 4.1 Create PoseDetector class
    - Create `src/opendance/pose/detector.py` with `PoseDetector` class
    - `__init__(config: PoseConfig)`: initialize MediaPipe PoseLandmarker with `RunningMode.VIDEO` from configured `model_path`; raise `FileNotFoundError` if model file missing
    - `detect(frame: np.ndarray, timestamp_ms: int) -> PoseResult`: convert BGR→RGB, run `detect_for_video()`, translate result to `PoseResult`; catch exceptions → return `PoseResult.empty()`
    - `close()`: release MediaPipe resources
    - Update `src/opendance/pose/__init__.py` to export `PoseDetector`
    - **Files:** `src/opendance/pose/detector.py`, `src/opendance/pose/__init__.py`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.8, 7.9, 7.10, 13.4_

  - [x] 4.2 Provision MediaPipe model asset
    - Add a `scripts/download_models.py` script that downloads `pose_landmarker_lite.task` from the official MediaPipe releases to `assets/models/pose_landmarker.task`
    - Add a `.gitkeep` or README in `assets/models/` documenting the model provenance and download instructions
    - Update project README to document model download step
    - **Files:** `scripts/download_models.py`, `assets/models/README.md`
    - _Requirements: 7.3_

  - [x]* 4.3 Write property tests for PoseDetector (mocked MediaPipe)
    - **Property 6: Pose detection produces valid result for any frame without exception**
    - Mock `mediapipe.tasks.vision.PoseLandmarker` to return predefined results or raise exceptions
    - Generate random BGR frames via hypothesis (arbitrary dimensions >= 1×1)
    - Verify detect() always returns a PoseResult, never raises
    - Verify detect() returns PoseResult.empty() when mock raises or returns empty
    - **Validates: Requirements 7.4, 7.8**
    - **Files:** `tests/unit/test_pose_detector.py`

- [ ] 5. Checkpoint - Verify configuration and data model layer
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement FrameWorker (QThread)
  - [x] 6.1 Create FrameWorker QThread class
    - Create `src/opendance/camera/frame_worker.py` with `FrameWorker(QThread)` class
    - Signals: `frame_ready(np.ndarray, PoseResult)`, `error_occurred(str)`
    - `__init__`: accept injected `capture`, `PoseDetector`, `FPSMonitor`, `consecutive_failure_threshold`
    - `run()`: tight loop calling `capture.read()`, incrementing/resetting failure counter, calling `fps_monitor.tick()`, calling `pose_detector.detect()`, emitting `frame_ready`; on threshold → emit `error_occurred` and exit
    - `request_stop()`: set `_running = False` to exit loop
    - `pause()` / `resume()`: use `threading.Event` to suspend/resume loop
    - Update `src/opendance/camera/__init__.py` to export `FrameWorker`
    - **Files:** `src/opendance/camera/frame_worker.py`, `src/opendance/camera/__init__.py`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 5.2_

  - [x]* 6.2 Write property tests for FrameWorker consecutive failure threshold
    - **Property 4: Consecutive failure threshold triggers error state**
    - Mock VideoCapture to return configurable sequences of (True, frame) and (False, None)
    - Use hypothesis to generate failure sequences with varying thresholds
    - Verify error_occurred emitted iff consecutive failures >= threshold
    - Verify counter resets on any successful read
    - **Validates: Requirements 5.2, 5.3, 5.5**
    - **Files:** `tests/unit/test_frame_worker.py`

- [ ] 7. Implement CameraManager (state machine and lifecycle)
  - [x] 7.1 Create CameraManager class
    - Create `src/opendance/camera/manager.py` with `CameraManager(QObject)` class
    - Signal: `state_changed(CameraState, str)`
    - `__init__(config: CameraConfig, pose_config: PoseConfig)`: store config, set initial state to INACTIVE
    - `start()`: create VideoCapture(device_index), set resolution, check isOpened(), create PoseDetector, FPSMonitor, FrameWorker; transition to ACTIVE or ERROR
    - `pause()`: ACTIVE → PAUSED, suspend FrameWorker
    - `resume()`: PAUSED → ACTIVE, resume FrameWorker
    - `stop()`: any state → INACTIVE, stop FrameWorker, release VideoCapture, clear resources
    - `cleanup()`: idempotent full resource release (called on app shutdown), close PoseDetector
    - Properties: `state`, `error_message`, `fps` (delegates to FPSMonitor)
    - Update `src/opendance/camera/__init__.py` to export `CameraManager`
    - **Files:** `src/opendance/camera/manager.py`, `src/opendance/camera/__init__.py`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 5.1, 5.3, 5.5, 5.6, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 13.1, 13.2, 13.3_

  - [x]* 7.2 Write property tests for CameraManager state machine
    - **Property 2: Successful camera open transitions to active with notification**
    - **Property 3: Stop from any state transitions to inactive with cleanup and notification**
    - **Property 1: Camera initialization uses configured device index**
    - Mock VideoCapture to control open/read success; verify state transitions
    - Verify state_changed signal emitted with correct (state, error_msg) for all transitions
    - Verify stop() is idempotent and always reaches INACTIVE
    - Verify configured device_index is passed to VideoCapture constructor
    - **Validates: Requirements 1.1, 1.2, 1.5, 3.2, 3.5, 3.7, 11.1, 11.2**
    - **Files:** `tests/unit/test_camera_manager.py`

  - [x]* 7.3 Write property tests for repeated start/stop resource integrity
    - **Property 11: Repeated start/stop cycles do not leak resources**
    - Use hypothesis to generate N (1..20) start/stop cycles
    - Verify VideoCapture.release() called exactly N times
    - Verify zero threads alive after final stop
    - **Validates: Requirements 11.1, 11.2, 11.5**
    - **Files:** `tests/unit/test_camera_manager.py`

- [ ] 8. Implement skeleton renderer
  - [x] 8.1 Create render_skeleton function
    - Create `src/opendance/ui/skeleton_renderer.py` with `POSE_CONNECTIONS` list and `render_skeleton()` pure function
    - Accept `frame`, `pose_result`, `visibility_threshold`, color params, radius, thickness
    - Draw landmarks with `cv2.circle()` only if visibility >= threshold
    - Draw bone connections with `cv2.line()` only if both endpoint landmarks meet threshold
    - Return frame unmodified if `pose_result.is_empty`
    - Update `src/opendance/ui/__init__.py` to export `render_skeleton`
    - **Files:** `src/opendance/ui/skeleton_renderer.py`, `src/opendance/ui/__init__.py`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [x]* 8.2 Write property tests for skeleton renderer visibility threshold
    - **Property 7: Skeleton rendering respects visibility threshold**
    - Generate random PoseResults and thresholds via hypothesis
    - Verify landmarks drawn iff visibility >= threshold (check pixel changes at landmark coordinates)
    - Verify bones drawn iff both endpoints meet threshold
    - Verify empty PoseResult → frame unchanged (byte-identical)
    - **Validates: Requirements 9.1, 9.2, 9.3**
    - **Files:** `tests/unit/test_skeleton_renderer.py`

- [ ] 9. Checkpoint - Verify core pipeline components
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Implement StatusIndicator widget
  - [x] 10.1 Create StatusIndicator QLabel
    - Create `src/opendance/ui/status_indicator.py` with `StatusIndicator(QLabel)` class
    - Define `_STATE_MESSAGES` dict mapping `CameraState` → human-readable string
    - Implement `update_state(state, error_message)` method: show error text for ERROR state, standard messages otherwise
    - Update `src/opendance/ui/__init__.py` to export `StatusIndicator`
    - **Files:** `src/opendance/ui/status_indicator.py`, `src/opendance/ui/__init__.py`
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x]* 10.2 Write unit tests for StatusIndicator
    - Test each CameraState maps to the correct human-readable message
    - Test ERROR state uses provided error_message string
    - Test "No camera found" message scenario
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6**
    - **Files:** `tests/unit/test_status_indicator.py`

- [ ] 11. Implement CameraWidget (display, controls, frame conversion)
  - [x] 11.1 Create CameraWidget class
    - Create `src/opendance/ui/camera_widget.py` with `CameraWidget(QWidget)` class
    - Layout: QVBoxLayout with QLabel for camera display on top, QHBoxLayout with Start/Stop QPushButtons and StatusIndicator on bottom
    - Connect Start button → `camera_manager.start()`, Stop button → `camera_manager.stop()`
    - Connect `camera_manager.state_changed` → `_on_state_changed` slot (enable/disable buttons per state)
    - Connect `frame_worker.frame_ready` → `_on_frame_ready` slot
    - `_on_frame_ready`: call `render_skeleton()`, convert BGR→RGB, create QImage, create QPixmap, scale with `Qt.KeepAspectRatio`, set on display label
    - When INACTIVE: show placeholder text; when PAUSED: keep last pixmap
    - Update `src/opendance/ui/__init__.py` to export `CameraWidget`
    - **Files:** `src/opendance/ui/camera_widget.py`, `src/opendance/ui/__init__.py`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 9.4, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

  - [x]* 11.2 Write property tests for UI control state and frame display
    - **Property 10: UI control state reflects Camera_State**
    - **Property 9: Frame display preserves aspect ratio with correct color conversion**
    - Test Start button enabled iff state in {INACTIVE, ERROR}
    - Test Stop button enabled iff state in {ACTIVE, PAUSED}
    - Generate random frame dimensions via hypothesis, verify display pixmap preserves aspect ratio
    - Verify BGR→RGB conversion applied correctly
    - **Validates: Requirements 6.5, 6.6, 12.2, 12.3**
    - **Files:** `tests/unit/test_camera_widget.py`

- [ ] 12. Integrate camera pipeline into main window
  - [x] 12.1 Extend main.py to create and wire camera pipeline
    - Import `CameraManager`, `CameraWidget` and config types
    - After loading config, create `CameraManager(config.camera_config, config.pose_config)`
    - Create `CameraWidget(camera_manager, config)` and set as `window.setCentralWidget(camera_widget)`
    - Connect `app.aboutToQuit` → `camera_manager.cleanup` for graceful shutdown
    - Remove or replace Phase 0 bare window placeholder
    - **Files:** `src/opendance/app/main.py`
    - _Requirements: 11.3, 11.4, 12.7_

  - [x]* 12.2 Write unit tests for main window integration
    - Test that CameraWidget is set as central widget
    - Test that aboutToQuit is connected to camera_manager.cleanup
    - Test that closing window triggers cleanup (mock CameraManager)
    - Use `QT_QPA_PLATFORM=offscreen` for headless testing
    - **Validates: Requirements 11.3, 11.4, 12.7**
    - **Files:** `tests/unit/test_main_integration.py`

- [x] 13. Final checkpoint - Full pipeline verification
  - Ensure all tests pass, ask the user if questions arise.
  - Verify no orphaned imports or missing exports
  - Verify `ruff check src/ tests/` passes
  - Verify `mypy src/` passes (or only has expected missing-import issues for mediapipe stubs)
  - Verify CI workflow would pass with `QT_QPA_PLATFORM=offscreen`

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All tests use mocked camera and mocked MediaPipe — no hardware needed
- The `hypothesis` library is added as a dev dependency in task 1.4
- `QT_QPA_PLATFORM=offscreen` is already configured in CI for headless widget tests
- Phase 0 architecture is preserved and extended, not replaced
- The MediaPipe model file is not committed to git; a download script is provided

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.4"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["1.5", "2.1", "2.2", "3.1"] },
    { "id": 3, "tasks": ["2.3", "3.2", "4.1", "4.2"] },
    { "id": 4, "tasks": ["4.3", "6.1"] },
    { "id": 5, "tasks": ["6.2", "7.1"] },
    { "id": 6, "tasks": ["7.2", "7.3", "8.1"] },
    { "id": 7, "tasks": ["8.2", "10.1"] },
    { "id": 8, "tasks": ["10.2", "11.1"] },
    { "id": 9, "tasks": ["11.2", "12.1"] },
    { "id": 10, "tasks": ["12.2"] }
  ]
}
```
