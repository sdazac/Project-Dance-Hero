"""Unit tests for FrameWorker with mocked VideoCapture and PoseDetector.

Property 4: Consecutive failure threshold triggers error state.
Tests use mocked inputs — no camera hardware required.
"""

import os
from unittest.mock import MagicMock, patch

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


class TestFrameWorkerTimestamps:
    """Timestamps are derived from real elapsed time and strictly increasing.

    Validates: Requirements 3.2, 8.3, 8.5
    """

    @staticmethod
    def _run_with_perf_sequence(
        qapp: QApplication,
        perf_values: list[float],
        frame_count: int,
    ) -> list[int]:
        """Run the worker with a controlled perf_counter sequence.

        The worker calls ``time.perf_counter()`` exactly once at loop entry
        (the ``start`` anchor) and once per successful read. ``perf_values``
        must therefore contain ``1 + frame_count`` entries: the first is the
        anchor, the rest are the per-iteration values.

        ``FPSMonitor`` is mocked so it does not consume from the patched
        ``perf_counter`` sequence — only the worker's own calls do. The mock's
        side effect repeats the final value defensively so any unexpected extra
        call does not raise ``StopIteration`` and mask the real assertions.

        Returns the list of ``timestamp_ms`` values passed to
        ``pose_detector.detect`` (the second positional argument).
        """
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        call_count = [0]

        def mock_read() -> tuple[bool, np.ndarray | None]:
            call_count[0] += 1
            # Stop the loop after enough successful frames have been produced.
            if call_count[0] >= frame_count:
                worker.request_stop()
            return (True, fake_frame)

        mock_capture = MagicMock()
        mock_capture.read.side_effect = mock_read

        mock_pose_detector = MagicMock()
        mock_pose_detector.detect.return_value = PoseResult.empty()
        # Mock the FPS monitor so its own perf_counter() call does not consume
        # from the controlled sequence driving the worker's timestamps.
        mock_fps_monitor = MagicMock()

        worker = FrameWorker(
            capture=mock_capture,
            pose_detector=mock_pose_detector,
            fps_monitor=mock_fps_monitor,
            consecutive_failure_threshold=10,
        )

        perf_iter = iter(perf_values)
        last_value = perf_values[-1]

        def next_perf() -> float:
            nonlocal last_value
            try:
                last_value = next(perf_iter)
            except StopIteration:
                pass
            return last_value

        with patch(
            "opendance.camera.frame_worker.time.perf_counter",
            side_effect=next_perf,
        ):
            worker.run()

        return [call.args[1] for call in mock_pose_detector.detect.call_args_list]

    def test_timestamps_derived_from_elapsed_time(self, qapp: QApplication) -> None:
        """Emitted timestamps equal int((perf_counter - start) * 1000)."""
        start = 100.0
        # Irregular elapsed times relative to the start anchor.
        per_iter = [100.011, 100.052, 100.058, 100.121]
        perf_values = [start, *per_iter]

        timestamps = self._run_with_perf_sequence(qapp, perf_values, frame_count=4)

        # Each emitted timestamp is the floor of elapsed-milliseconds since the
        # loop-entry anchor — i.e. real elapsed time, not a fixed per-frame step.
        expected = [int((value - start) * 1000) for value in per_iter]
        assert timestamps == expected

    def test_timestamps_strictly_monotonic(self, qapp: QApplication) -> None:
        """Timestamps strictly increase across frames (Requirement 3.2)."""
        start = 200.0
        per_iter = [200.005, 200.006, 200.100, 200.101, 200.500]
        perf_values = [start, *per_iter]

        timestamps = self._run_with_perf_sequence(qapp, perf_values, frame_count=5)

        for previous, current in zip(timestamps, timestamps[1:]):
            assert current > previous

    def test_timestamps_not_fixed_step(self, qapp: QApplication) -> None:
        """Timestamps reflect irregular elapsed time, not a uniform 33ms step."""
        start = 1000.0
        # Elapsed times producing irregular per-frame steps (~11, 39, 6, 89 ms),
        # deliberately unlike the old fixed +33ms increment.
        per_iter = [1000.011, 1000.050, 1000.056, 1000.145]
        perf_values = [start, *per_iter]

        timestamps = self._run_with_perf_sequence(qapp, perf_values, frame_count=4)

        expected = [int((value - start) * 1000) for value in per_iter]
        assert timestamps == expected
        deltas = [b - a for a, b in zip(timestamps, timestamps[1:])]
        # The steps are irregular (more than one distinct value) and none of
        # them equal the old fixed +33ms increment.
        assert len(set(deltas)) > 1
        assert 33 not in deltas

    def test_collision_guard_preserves_strict_monotonicity(
        self, qapp: QApplication
    ) -> None:
        """Duplicate integer-ms values are bumped by +1 to stay strictly increasing."""
        start = 500.0
        # Frames 1-3 share the same elapsed time, so all floor to the same raw
        # millisecond, forcing the +1 ms collision guard to fire twice in a row.
        collide = 500.020
        per_iter = [collide, collide, collide, 500.030]
        perf_values = [start, *per_iter]

        timestamps = self._run_with_perf_sequence(qapp, perf_values, frame_count=4)

        raw = int((collide - start) * 1000)
        # Raw floored values would be [raw, raw, raw, raw+10]; the guard bumps
        # the colliding frames by +1 ms each to preserve strict monotonicity.
        assert timestamps[0] == raw
        assert timestamps[1] == raw + 1
        assert timestamps[2] == raw + 2
        for previous, current in zip(timestamps, timestamps[1:]):
            assert current > previous
