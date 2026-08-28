"""Camera lifecycle manager for OpenDance AI.

Manages camera discovery, initialization, state transitions, and resource cleanup.
"""

import logging

import cv2
from PySide6.QtCore import QObject, Signal

from opendance.camera.fps_monitor import FPSMonitor
from opendance.camera.frame_worker import FrameWorker
from opendance.camera.state import CameraState
from opendance.config.models import CameraConfig, PoseConfig
from opendance.pose.detector import PoseDetector

logger = logging.getLogger(__name__)


class CameraManager(QObject):
    """Manages camera lifecycle: discovery, open, state transitions, cleanup.

    Signals:
        state_changed(CameraState, str): Emitted on every state transition.
            The str is the error description (empty string if no error).
    """

    state_changed = Signal(object, str)  # (CameraState, error_message)

    def __init__(
        self,
        camera_config: CameraConfig,
        pose_config: PoseConfig,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._camera_config = camera_config
        self._pose_config = pose_config
        self._active_device_index: int = camera_config.device_index
        self._state = CameraState.INACTIVE
        self._error_message = ""
        self._capture: cv2.VideoCapture | None = None
        self._frame_worker: FrameWorker | None = None
        self._pose_detector: PoseDetector | None = None
        self._fps_monitor = FPSMonitor()

    @property
    def state(self) -> CameraState:
        """Current camera state."""
        return self._state

    @property
    def error_message(self) -> str:
        """Error description when in ERROR state, empty otherwise."""
        return self._error_message

    @property
    def fps(self) -> float:
        """Current measured FPS from FPSMonitor."""
        return self._fps_monitor.fps

    @property
    def frame_worker(self) -> FrameWorker | None:
        """Active FrameWorker instance, or None if not running."""
        return self._frame_worker

    @property
    def device_index(self) -> int:
        """The camera device index currently in use."""
        return self._active_device_index

    def _set_state(self, new_state: CameraState, error_msg: str = "") -> None:
        """Transition to a new state and emit notification."""
        self._state = new_state
        self._error_message = error_msg
        self.state_changed.emit(new_state, error_msg)
        if error_msg:
            logger.info("Camera state → %s: %s", new_state.name, error_msg)
        else:
            logger.info("Camera state → %s", new_state.name)

    def start(self) -> None:
        """Discover and open camera. Transitions INACTIVE/ERROR → ACTIVE or → ERROR."""
        if self._state == CameraState.ACTIVE:
            return

        # Initialize PoseDetector
        try:
            self._pose_detector = PoseDetector(self._pose_config)
        except FileNotFoundError as exc:
            self._set_state(CameraState.ERROR, f"Pose model not found: {exc}")
            return
        except Exception as exc:
            self._set_state(CameraState.ERROR, f"Pose initialization failed: {exc}")
            return

        # Open camera
        device_index = self._active_device_index
        capture = cv2.VideoCapture(device_index)

        if not capture.isOpened():
            self._set_state(
                CameraState.ERROR,
                f"Could not open camera (device {device_index}).",
            )
            if self._pose_detector:
                self._pose_detector.close()
                self._pose_detector = None
            return

        # Attempt to set requested resolution
        req_w = self._camera_config.resolution_width
        req_h = self._camera_config.resolution_height
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, req_w)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, req_h)

        actual_w = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if actual_w != req_w or actual_h != req_h:
            logger.warning(
                "Requested resolution %dx%d not supported; using %dx%d.",
                req_w,
                req_h,
                actual_w,
                actual_h,
            )

        self._capture = capture
        self._fps_monitor.reset()

        # Start worker thread
        self._frame_worker = FrameWorker(
            capture=self._capture,
            pose_detector=self._pose_detector,
            fps_monitor=self._fps_monitor,
            consecutive_failure_threshold=self._camera_config.consecutive_failure_threshold,
        )
        self._frame_worker.error_occurred.connect(self._on_worker_error)
        self._frame_worker.start()

        self._set_state(CameraState.ACTIVE)
        logger.info(
            "Camera opened: device=%d, resolution=%dx%d",
            device_index,
            actual_w,
            actual_h,
        )

    def pause(self) -> None:
        """Suspend frame acquisition. Transitions ACTIVE → PAUSED."""
        if self._state != CameraState.ACTIVE:
            return
        if self._frame_worker:
            self._frame_worker.pause()
        self._set_state(CameraState.PAUSED)

    def resume(self) -> None:
        """Resume frame acquisition. Transitions PAUSED → ACTIVE."""
        if self._state != CameraState.PAUSED:
            return
        if self._frame_worker:
            self._frame_worker.resume()
        self._set_state(CameraState.ACTIVE)

    def stop(self) -> None:
        """Stop camera and release resources. Any state → INACTIVE."""
        self._release_resources()
        self._set_state(CameraState.INACTIVE)

    def restart(self, device_index: int | None = None) -> None:
        """Release the camera and re-open it, optionally on a new device index.

        Safe to call from the UI. Emits state_changed like start(). If
        device_index is provided it becomes the active index for this and
        future starts.
        """
        if device_index is not None:
            self._active_device_index = device_index
        self._release_resources()
        self._state = CameraState.INACTIVE
        self.start()

    def cleanup(self) -> None:
        """Release all resources. Called on application shutdown."""
        self._release_resources()
        logger.info("CameraManager cleanup complete.")

    def _release_resources(self) -> None:
        """Internal: stop worker, release capture, close pose detector."""
        # Stop worker thread
        if self._frame_worker is not None:
            self._frame_worker.request_stop()
            self._frame_worker.wait(5000)  # Wait up to 5 seconds
            if self._frame_worker.isRunning():
                logger.warning("FrameWorker did not terminate within timeout.")
            self._frame_worker = None

        # Release VideoCapture
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception as exc:
                logger.warning("Error releasing VideoCapture: %s", exc)
            self._capture = None

        # Close PoseDetector
        if self._pose_detector is not None:
            try:
                self._pose_detector.close()
            except Exception as exc:
                logger.warning("Error closing PoseDetector: %s", exc)
            self._pose_detector = None

        self._fps_monitor.reset()

    def _on_worker_error(self, error_msg: str) -> None:
        """Handle error from FrameWorker (consecutive failure threshold reached)."""
        self._release_resources()
        self._set_state(CameraState.ERROR, error_msg)
