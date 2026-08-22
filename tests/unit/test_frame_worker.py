"""Unit tests for FrameWorker with mocked VideoCapture and PoseDetector.

Property 4: Consecutive failure threshold triggers error state.
Tests use mocked inputs — no camera hardware required.
"""

import os
from unittest.mock import MagicMock

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from opendance.camera.fps_monitor import FPSMonitor
from opendance.camera.frame_worker import FrameWorker
from opendance.pose.result import PoseResult


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """Ensure QApplication exists for signal tests."""
    import sys

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestFrameWorkerConsecutiveFailures:
    """Test that consecutive failures trigger error_occurred signal."""

    def test_error_emitted_at_threshold(self, qapp: QApplication) -> None:
        """error_occurred emitted when consecutive failures reach threshold."""
        threshold = 5
        mock_capture = MagicMock()
        mock_capture.read.return_value = (False, None)

        mock_pose_detector = MagicMock()
        fps_monitor = FPSMonitor()

        worker = FrameWorker(
            capture=mock_capture,
            pose_detector=mock_pose_detector,
            fps_monitor=fps_monitor,
            consecutive_failure_threshold=threshold,
        )

        errors: list[str] = []
        worker.error_occurred.connect(errors.append)

        worker.run()  # Run synchronously (not in a thread) for testing

        assert len(errors) == 1
        assert "5" in errors[0]
        assert mock_capture.read.call_count == threshold

    def test_counter_resets_on_success(self, qapp: QApplication) -> None:
        """Consecutive failure counter resets after a successful read."""
        threshold = 5
        # Pattern: 3 failures, 1 success, 3 failures, 1 success, ...
        # Should never reach threshold of 5
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        call_count = [0]
        max_calls = 20

        def mock_read() -> tuple[bool, np.ndarray | None]:
            call_count[0] += 1
            if call_count[0] > max_calls:
                # Stop the worker by signaling stop after enough calls
                worker.request_stop()
                return (False, None)
            # Fail every 4th call pattern: F F F S F F F S ...
            if call_count[0] % 4 == 0:
                return (True, fake_frame)
            return (False, None)

        mock_capture = MagicMock()
        mock_capture.read.side_effect = mock_read

        mock_pose_detector = MagicMock()
        mock_pose_detector.detect.return_value = PoseResult.empty()
        fps_monitor = FPSMonitor()

        worker = FrameWorker(
            capture=mock_capture,
            pose_detector=mock_pose_detector,
            fps_monitor=fps_monitor,
            consecutive_failure_threshold=threshold,
        )

        errors: list[str] = []
        worker.error_occurred.connect(errors.append)

        worker.run()

        # No error should have been emitted because counter resets
        assert len(errors) == 0


class TestFrameWorkerFrameEmission:
    """Test that frame_ready signal is emitted on successful reads."""

    def test_frame_ready_emitted_on_success(self, qapp: QApplication) -> None:
        """frame_ready emitted with frame and PoseResult on successful read."""
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        call_count = [0]

        def mock_read() -> tuple[bool, np.ndarray | None]:
            call_count[0] += 1
            if call_count[0] > 3:
                worker.request_stop()
                return (False, None)
            return (True, fake_frame)

        mock_capture = MagicMock()
        mock_capture.read.side_effect = mock_read

        mock_pose_detector = MagicMock()
        mock_pose_detector.detect.return_value = PoseResult.empty()
        fps_monitor = FPSMonitor()

        worker = FrameWorker(
            capture=mock_capture,
            pose_detector=mock_pose_detector,
            fps_monitor=fps_monitor,
            consecutive_failure_threshold=10,
        )

        frames_received: list[tuple[object, object]] = []
        worker.frame_ready.connect(lambda f, p: frames_received.append((f, p)))

        worker.run()

        assert len(frames_received) == 3
        assert mock_pose_detector.detect.call_count == 3


class TestFrameWorkerPauseResume:
    """Test pause/resume behavior."""

    def test_request_stop_exits_loop(self, qapp: QApplication) -> None:
        """request_stop() causes the worker to exit."""
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        call_count = [0]

        def mock_read() -> tuple[bool, np.ndarray | None]:
            call_count[0] += 1
            if call_count[0] >= 2:
                worker.request_stop()
            return (True, fake_frame)

        mock_capture = MagicMock()
        mock_capture.read.side_effect = mock_read

        mock_pose_detector = MagicMock()
        mock_pose_detector.detect.return_value = PoseResult.empty()
        fps_monitor = FPSMonitor()

        worker = FrameWorker(
            capture=mock_capture,
            pose_detector=mock_pose_detector,
            fps_monitor=fps_monitor,
            consecutive_failure_threshold=10,
        )

        worker.run()

        # Worker should have stopped after 2 reads
        assert call_count[0] >= 2
