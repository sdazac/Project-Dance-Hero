# Requirements Document

## Introduction

This specification defines Phase 1 of OpenDance AI — Camera Capture, Real-Time Pose Detection, and Minimal Visualization. Phase 1 builds upon the project foundation (Phase 0) to deliver the first domain-specific functionality: acquiring webcam frames without blocking the UI, running MediaPipe Pose Landmarker on those frames in real time, and rendering a skeleton overlay on the camera feed within the PySide6 application.

Phase 1 scope ends at raw pose detection and visualization. It does NOT include pose normalization, reference video loading, motion feature extraction, temporal alignment, scoring, grading, Practice mode, or Arcade mode. Those capabilities are addressed in subsequent phases.

## Glossary

- **Camera_Manager**: The module responsible for discovering available cameras, initializing OpenCV VideoCapture, managing camera lifecycle states, and providing frames to consumers.
- **Frame_Worker**: The background worker thread that acquires frames from the camera and runs pose detection without blocking the Qt UI event loop.
- **Camera_State**: An enumeration representing the current operational state of the camera subsystem (e.g., inactive, active, paused, error).
- **FPS_Monitor**: The component that measures the actual frame acquisition rate of the camera.
- **Pose_Detector**: The module responsible for initializing MediaPipe Pose Landmarker, running pose inference on camera frames, and producing landmark results with confidence data.
- **Pose_Result**: The structured output of a single pose detection, containing landmark coordinates (normalized and world), visibility values, and confidence scores for each detected landmark.
- **Skeleton_Renderer**: The component that draws pose landmarks and bone connections onto a camera frame for visual feedback.
- **Camera_Widget**: The PySide6 widget responsible for displaying the live camera feed (with optional skeleton overlay) in the main application window.
- **Status_Indicator**: The UI element that communicates the current camera state and any errors to the user in human-readable form.

## Requirements

### Requirement 1: Camera Discovery and Initialization

**User Story:** As a user, I want the application to find and open my webcam, so that I can see my live camera feed in the application.

#### Acceptance Criteria

1. WHEN the user initiates camera start, THE Camera_Manager SHALL attempt to discover and open an available camera device using OpenCV VideoCapture.
2. WHEN a camera is successfully opened, THE Camera_Manager SHALL transition Camera_State to active.
3. IF no camera device is available, THEN THE Camera_Manager SHALL transition Camera_State to error and provide a descriptive error reason indicating no camera was found.
4. IF the requested camera device fails to open, THEN THE Camera_Manager SHALL transition Camera_State to error and provide a descriptive error reason indicating the camera could not be initialized.
5. THE Camera_Manager SHALL accept a configurable camera device index via the configuration system rather than hardcoding a specific device number.
6. THE Camera_Manager SHALL accept configurable camera resolution (width, height) via the configuration system. IF the camera does not support the requested resolution, THE Camera_Manager SHALL use the camera's default resolution and log a warning.
7. THE Camera_Manager SHALL log camera discovery and initialization events using the application logging system without logging raw frame data.

### Requirement 2: Non-Blocking Frame Acquisition

**User Story:** As a user, I want the camera feed to update smoothly without freezing the application interface, so that I can interact with UI controls while the camera is running.

#### Acceptance Criteria

1. WHILE Camera_State is active, THE Frame_Worker SHALL acquire frames from the camera on a background thread separate from the Qt UI event loop.
2. WHILE Camera_State is active, THE Frame_Worker SHALL make each newly acquired frame available to consumers without requiring the UI thread to wait for camera I/O.
3. THE Frame_Worker SHALL NOT block the Qt event loop during frame acquisition, pose detection, frame transfer, or any camera I/O operation.
4. WHEN a new frame is acquired and pose detection is complete, THE Frame_Worker SHALL signal frame availability using a thread-safe mechanism compatible with PySide6 (e.g., Qt signal), delivering both the frame and its corresponding Pose_Result to the UI thread.
5. IF a frame acquisition attempt fails while Camera_State is active, THEN THE Frame_Worker SHALL log the failure and continue attempting to acquire subsequent frames rather than terminating immediately.
6. THE Pose_Detector SHALL run pose inference on the Frame_Worker's background thread, NOT on the Qt UI event loop thread, to prevent UI blocking during inference.

### Requirement 3: Camera State Management

**User Story:** As a developer, I want well-defined camera states, so that the UI and other components can react appropriately to camera status changes.

#### Acceptance Criteria

1. THE Camera_Manager SHALL represent Camera_State using an explicit enumeration with at minimum the following states: inactive, active, paused, error.
2. WHEN the user requests the camera to start, THE Camera_Manager SHALL transition from inactive to active upon successful initialization.
3. WHEN the user requests the camera to pause, THE Camera_Manager SHALL transition from active to paused and suspend frame acquisition.
4. WHEN the user requests the camera to resume from paused, THE Camera_Manager SHALL transition from paused to active and resume frame acquisition.
5. WHEN the user requests the camera to stop, THE Camera_Manager SHALL transition to inactive from any operational state and release camera resources.
6. IF an unrecoverable error occurs during camera operation, THEN THE Camera_Manager SHALL transition to error state and preserve a human-readable error description.
7. WHEN Camera_State changes, THE Camera_Manager SHALL emit a notification so that interested components (UI, logging) can react to the state transition.
8. WHILE Camera_State is paused, THE Pose_Detector SHALL retain its initialized model instance without releasing resources, so that resuming does not require reinitialization.

### Requirement 4: Camera FPS Measurement

**User Story:** As a developer, I want to measure the actual camera frame rate, so that I can monitor pipeline performance and detect degradation.

#### Acceptance Criteria

1. WHILE Camera_State is active, THE FPS_Monitor SHALL calculate the actual frame acquisition rate based on elapsed time between successfully acquired frames.
2. THE FPS_Monitor SHALL provide the current measured FPS value to consumers upon request.
3. THE FPS_Monitor SHALL use a rolling window or exponential smoothing approach so that the reported FPS reflects recent performance rather than a cumulative lifetime average.
4. THE FPS_Monitor SHALL NOT introduce meaningful overhead that would reduce the effective frame rate.

### Requirement 5: Camera Failure Handling

**User Story:** As a user, I want the application to handle camera problems gracefully, so that the application remains usable and I understand what went wrong.

#### Acceptance Criteria

1. IF the camera device becomes unavailable during active operation (e.g., physically disconnected), THEN THE Camera_Manager SHALL detect the failure, transition to error state, and provide a descriptive error reason.
2. IF frame acquisition fails for a configurable number of consecutive attempts (default: 10), THEN THE Camera_Manager SHALL treat the failure as unrecoverable and transition to error state. The consecutive-failure threshold SHALL be configurable via the configuration system.
3. IF the camera fails, THEN THE Camera_Manager SHALL NOT cause the application to crash or produce an unhandled exception that terminates the process.
4. IF the camera transitions to error state, THEN THE Status_Indicator SHALL display a user-facing error message describing the problem in non-technical language.
5. IF the camera fails, THEN THE Camera_Manager SHALL release any partially held camera resources to avoid resource leaks.
6. THE Camera_Manager SHALL log technical details of camera failures using the application logging system for developer diagnosis.

### Requirement 6: Camera Start and Stop Controls

**User Story:** As a user, I want start and stop buttons in the application, so that I can control when the camera is active.

#### Acceptance Criteria

1. THE Camera_Widget SHALL provide a user-accessible control to start the camera when Camera_State is inactive or error.
2. THE Camera_Widget SHALL provide a user-accessible control to stop the camera when Camera_State is active or paused.
3. WHEN the user activates the start control, THE Camera_Widget SHALL initiate camera discovery and frame acquisition.
4. WHEN the user activates the stop control, THE Camera_Widget SHALL stop frame acquisition and release camera resources.
5. WHILE Camera_State is active, THE start control SHALL be disabled or hidden to prevent redundant start requests.
6. WHILE Camera_State is inactive or error, THE stop control SHALL be disabled or hidden to prevent redundant stop requests.

### Requirement 7: Pose Detection Initialization and Inference

**User Story:** As a user, I want my body pose detected from the camera feed, so that the application can track my movements in real time.

#### Acceptance Criteria

1. THE Pose_Detector SHALL initialize MediaPipe Pose Landmarker once during setup and reuse the initialized instance for all subsequent frames.
2. THE Pose_Detector SHALL NOT reinitialize the MediaPipe model on every frame.
3. THE Pose_Detector SHALL load the MediaPipe Pose Landmarker model from a bundled model file located in the project's `assets/models/` directory. The model file path SHALL be configurable via the configuration system.
4. WHEN a camera frame is available, THE Pose_Detector SHALL run pose detection on the frame and produce a Pose_Result.
5. THE Pose_Result SHALL contain the normalized landmark coordinates (image-space) for all detected landmarks as provided by MediaPipe.
6. THE Pose_Result SHALL contain world landmark coordinates (meter-space, hip-centered) when provided by MediaPipe Pose Landmarker, for consumption by future phases.
7. THE Pose_Result SHALL contain the visibility and confidence values for each detected landmark as provided by MediaPipe.
8. IF pose detection fails on a given frame (e.g., no body detected), THEN THE Pose_Detector SHALL indicate an empty or absent result for that frame without raising an unhandled exception.
9. THE Pose_Detector SHALL operate at a rate that allows real-time processing of camera frames without introducing visible lag to the user.
10. THE Pose_Detector SHALL log pose detection initialization and critical errors using the application logging system without logging raw frame pixel data.

### Requirement 8: Pose Confidence and Visibility Preservation

**User Story:** As a developer, I want per-landmark confidence and visibility data preserved, so that downstream components can make informed decisions about landmark reliability.

#### Acceptance Criteria

1. FOR EACH detected landmark, THE Pose_Result SHALL preserve the visibility score as reported by MediaPipe.
2. FOR EACH detected landmark, THE Pose_Result SHALL preserve the presence confidence score as reported by MediaPipe.
3. THE Pose_Result SHALL use a structured data representation (e.g., dataclass or typed object) that provides named or typed access to landmark data (coordinate, visibility, confidence per landmark), while preserving compatibility with the MediaPipe Pose Landmarker landmark index scheme.
4. THE Pose_Result SHALL preserve the original landmark ordering consistent with the MediaPipe Pose Landmarker landmark indices.
5. FOR EACH detected landmark, THE Pose_Result SHALL preserve world coordinates (x, y, z in meters) when available from MediaPipe.

### Requirement 9: Real-Time Skeleton Overlay

**User Story:** As a user, I want to see my detected body skeleton drawn on the camera feed, so that I can verify pose detection is working and see which body parts are tracked.

#### Acceptance Criteria

1. WHEN a Pose_Result contains detected landmarks, THE Skeleton_Renderer SHALL draw landmark points on the corresponding camera frame at their detected positions.
2. WHEN a Pose_Result contains detected landmarks, THE Skeleton_Renderer SHALL draw bone connections between anatomically adjacent landmarks to form a visible skeleton.
3. THE Skeleton_Renderer SHALL only draw landmarks whose visibility exceeds a configurable minimum threshold (default: 0.5). Bone connections SHALL only be drawn when both connected landmarks meet the visibility threshold.
4. THE Skeleton_Renderer SHALL render the skeleton overlay directly onto the frame image that is displayed in the Camera_Widget.
5. WHEN no pose is detected in a frame, THE Skeleton_Renderer SHALL display the camera frame without any skeleton overlay rather than displaying stale skeleton data.
6. THE Skeleton_Renderer SHALL operate fast enough that rendering does not introduce visible delay between frame acquisition and display.

### Requirement 10: Camera Status Indication

**User Story:** As a user, I want to see the current camera status in the application, so that I know whether the camera is working, paused, or experiencing an error.

#### Acceptance Criteria

1. THE Status_Indicator SHALL display a human-readable status message reflecting the current Camera_State.
2. WHILE Camera_State is active, THE Status_Indicator SHALL indicate that the camera is operational (e.g., "Camera active").
3. WHILE Camera_State is inactive, THE Status_Indicator SHALL indicate that the camera is not running.
4. WHILE Camera_State is paused, THE Status_Indicator SHALL indicate that the camera is paused.
5. WHILE Camera_State is error, THE Status_Indicator SHALL display the error description provided by the Camera_Manager in user-understandable language.
6. IF the camera transitions to error due to no camera being found, THEN THE Status_Indicator SHALL display a message such as "No camera found" rather than a technical exception trace.

### Requirement 11: Resource Cleanup

**User Story:** As a user, I want the application to properly release camera and AI model resources, so that my system resources are freed when I stop the camera or exit the application.

#### Acceptance Criteria

1. WHEN the user stops the camera, THE Camera_Manager SHALL release the OpenCV VideoCapture resource.
2. WHEN the user stops the camera, THE Frame_Worker SHALL terminate its background thread cleanly without leaving orphaned threads.
3. WHEN the application is closed, THE Camera_Manager SHALL release all camera resources regardless of the current Camera_State.
4. WHEN the application is closed, THE Pose_Detector SHALL release the MediaPipe Pose Landmarker resources.
5. THE Camera_Manager SHALL ensure that repeated start/stop cycles do not accumulate unreleased resources or orphaned threads.
6. IF resource cleanup encounters an error, THEN THE Camera_Manager SHALL log the error and continue the cleanup process for remaining resources rather than aborting.

### Requirement 12: Webcam Feed Display Widget

**User Story:** As a user, I want to see my live webcam feed in the application window, so that I can see myself while the application tracks my movements.

#### Acceptance Criteria

1. THE Camera_Widget SHALL display live camera frames in the main application window as they are acquired.
2. THE Camera_Widget SHALL scale the displayed frame to fit the available widget area while preserving the original aspect ratio.
3. THE Camera_Widget SHALL convert camera frames from OpenCV BGR format to the format required by PySide6 for display.
4. WHEN Camera_State is inactive, THE Camera_Widget SHALL display a placeholder or blank area rather than a stale frame from a previous session.
5. WHEN Camera_State is paused, THE Camera_Widget SHALL display the last successfully acquired frame (frozen) rather than a blank placeholder.
6. THE Camera_Widget SHALL update the displayed frame at the rate frames are acquired without accumulating a backlog of undisplayed frames.
7. THE Camera_Widget SHALL be embedded as the central widget in the existing main application window established by Phase 0, replacing the placeholder content.

### Requirement 13: Privacy and Data Locality

**User Story:** As a user, I want my camera data to remain local on my machine, so that my privacy is protected.

#### Acceptance Criteria

1. THE Camera_Manager SHALL process all camera frames locally and SHALL NOT transmit frame data to any external service or network endpoint.
2. THE Camera_Manager SHALL NOT persist or record camera frames to disk unless a future recording feature is explicitly implemented and activated by the user.
3. THE application logging system SHALL NOT log raw camera frame pixel data or image content at any log level.
4. THE Pose_Detector SHALL perform all pose inference locally using the on-device MediaPipe model without requiring network access.

### Requirement 14: Phase 1 Scope Boundaries

**User Story:** As a developer, I want explicit boundaries on what Phase 1 delivers, so that implementation remains focused on camera capture, pose detection, and minimal visualization without scope creep.

#### Acceptance Criteria

1. THE Phase 1 implementation SHALL NOT include pose normalization or body-relative coordinate transformation.
2. THE Phase 1 implementation SHALL NOT include reference video loading, playback, or analysis.
3. THE Phase 1 implementation SHALL NOT include motion feature extraction such as velocity, acceleration, or joint angles.
4. THE Phase 1 implementation SHALL NOT include temporal alignment between user and reference motion.
5. THE Phase 1 implementation SHALL NOT include scoring, grading, combo, or event rating logic.
6. THE Phase 1 implementation SHALL NOT include Practice mode or Arcade mode.
7. THE Phase 1 implementation SHALL NOT include any pipeline stages beyond raw pose detection and skeleton visualization.

### Requirement 15: Configuration System Extension

**User Story:** As a developer, I want Phase 1 camera and pose settings managed through the existing configuration system, so that configurable values are not hardcoded and follow the same patterns established in Phase 0.

#### Acceptance Criteria

1. THE configuration system SHALL be extended with a `[camera]` section in defaults.toml containing: device_index (integer, default: 0), resolution_width (integer, default: 640), resolution_height (integer, default: 480), consecutive_failure_threshold (integer, default: 10).
2. THE configuration system SHALL be extended with a `[pose]` section in defaults.toml containing: model_path (string, default: "assets/models/pose_landmarker.task"), skeleton_visibility_threshold (float, default: 0.5).
3. THE AppConfig dataclass SHALL be extended with new frozen dataclass fields for camera and pose configuration, following the same pattern as ScoringThresholds and ScoringWeights.
4. THE configuration system SHALL validate camera and pose configuration values using the same type-checking and range-validation mechanisms established in Phase 0.
5. User overrides for camera and pose settings SHALL follow the same TOML merge semantics as scoring configuration (partial overrides, per-key fallback to defaults).

### Requirement 16: Testability Without Hardware

**User Story:** As a developer, I want to test camera and pose detection modules in CI without physical camera hardware, so that automated tests remain reliable on headless environments.

#### Acceptance Criteria

1. THE Camera_Manager SHALL be designed so that the camera input source can be substituted with a mock or synthetic frame provider for testing purposes.
2. THE Pose_Detector SHALL be designed so that pose inference can be tested with pre-recorded or synthetic frame data without requiring a live camera.
3. Unit tests for Camera_Manager, Frame_Worker, Pose_Detector, Skeleton_Renderer, and Camera_Widget SHALL NOT require physical camera hardware or GPU access.
4. Unit tests SHALL use mocked or synthetic inputs to verify state transitions, frame processing logic, and error handling independently of hardware availability.
