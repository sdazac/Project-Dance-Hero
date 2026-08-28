"""Background frame acquisition and pose detection worker thread."""

import logging
import threading
import time
from typing import Any

from PySide6.QtCore import QThread, Signal

from opendance.camera.fps_monitor import FPSMonitor
from opendance.pose.detector import PoseDetector

logger = logging.getLogger(__name__)


class FrameWorker(QThread):
    """Background thread: acquires frames, runs pose detection, emits results.

    Signals:
        frame_ready(np.ndarray, PoseResult): Frame + pose result available.
        error_occurred(str): Consecutive failures exceeded threshold.
    """

    frame_ready = Signal(object, object)  # (np.ndarray, PoseResult)
    error_occurred = Signal(str)

    def __init__(
        self,
        capture: Any,  # cv2.VideoCapture (typed as Any for testability)
        pose_detector: PoseDetector,
        fps_monitor: FPSMonitor,
        consecutive_failure_threshold: int = 10,
    ) -> None:
        super().__init__()
        self._capture = capture
        self._pose_detector = pose_detector
        self._fps_monitor = fps_monitor
        self._consecutive_failure_threshold = consecutive_failure_threshold
        self._running = False
        self._paused = threading.Event()
        self._paused.set()  # Not paused initially
        self._timestamp_ms = 0

    def run(self) -> None:
        """Main acquisition loop. Runs until request_stop() is called."""
        self._running = True
        consecutive_failures = 0
        # Anchor timestamps to real elapsed time so alignment reflects actual
        # playback, not a fixed per-frame step (Requirement 3.2).
        start = time.perf_counter()
        logger.info("FrameWorker started.")

        while self._running:
            # Wait if paused
            self._paused.wait()
            if not self._running:
                break

            try:
                ok, frame = self._capture.read()
            except Exception as exc:
                logger.warning("Frame acquisition exception: %s", exc)
                ok = False
                frame = None

            if not ok or frame is None:
                consecutive_failures += 1
                logger.debug(
                    "Frame acquisition failed (%d/%d).",
                    consecutive_failures,
                    self._consecutive_failure_threshold,
                )
                if consecutive_failures >= self._consecutive_failure_threshold:
                    error_msg = (
                        f"Camera failed after {consecutive_failures} "
                        f"consecutive read failures."
                    )
                    logger.error(error_msg)
                    self.error_occurred.emit(error_msg)
                    break
                continue

            # Successful read — reset failure counter
            consecutive_failures = 0
            self._fps_monitor.tick()

            # Derive the timestamp from real elapsed time.
            timestamp_ms = int((time.perf_counter() - start) * 1000)
            # MediaPipe VIDEO mode requires strictly increasing timestamps; if a
            # fast loop produces a duplicate/earlier value, bump by +1 ms.
            if timestamp_ms <= self._timestamp_ms:
                timestamp_ms = self._timestamp_ms + 1
            self._timestamp_ms = timestamp_ms

            # Run pose detection on worker thread (non-blocking for UI)
            pose_result = self._pose_detector.detect(frame, self._timestamp_ms)

            # Emit to UI thread
            self.frame_ready.emit(frame, pose_result)

        logger.info("FrameWorker stopped.")

    def request_stop(self) -> None:
        """Signal the worker to exit its loop gracefully."""
        self._running = False
        self._paused.set()  # Unblock if paused

    def pause(self) -> None:
        """Suspend frame acquisition without releasing resources."""
        self._paused.clear()
        logger.info("FrameWorker paused.")

    def resume(self) -> None:
        """Resume frame acquisition from paused state."""
        self._paused.set()
        logger.info("FrameWorker resumed.")
