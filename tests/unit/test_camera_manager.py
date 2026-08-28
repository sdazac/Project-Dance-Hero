"""Unit tests for CameraManager state machine and lifecycle.

Property 1: Camera initialization uses configured device index.
Property 2: Successful camera open transitions to active with notification.
Property 3: Stop from any state transitions to inactive with cleanup and notification.
Property 11: Repeated start/stop cycles do not leak resources.

All tests use mocked VideoCapture and PoseDetector — no camera hardware required.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from opendance.camera.manager import CameraManager
from opendance.camera.state import CameraState
from opendance.config.models import CameraConfig, PoseConfig


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """Ensure QApplication exists for signal tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture()
def mock_pose_detector() -> MagicMock:
    """Create a mock PoseDetector."""
    detector = MagicMock()
    detector.detect.return_value = MagicMock(is_empty=True, landmarks=(), world_landmarks=())
    return detector


@pytest.fixture()
def camera_config() -> CameraConfig:
    """Default camera config for tests."""
    return CameraConfig(device_index=2, resolution_width=640, resolution_height=480)


@pytest.fixture()
def pose_config(tmp_path: Path) -> PoseConfig:
    """Pose config with a fake model file."""
    model_file = tmp_path / "fake_model.task"
    model_file.write_bytes(b"fake")
    return PoseConfig(model_path=str(model_file))


class TestCameraManagerInit:
    """Test initial state and configuration."""

    def test_initial_state_is_inactive(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        manager = CameraManager(camera_config, pose_config)
        assert manager.state == CameraState.INACTIVE
        assert manager.error_message == ""


class TestCameraManagerStart:
    """Property 1 & 2: start uses configured device_index and transitions to ACTIVE."""

    def test_uses_configured_device_index(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        """VideoCapture is called with the configured device_index."""
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = True
        mock_capture.get.return_value = 640  # resolution query

        with patch("opendance.camera.manager.cv2.VideoCapture", return_value=mock_capture) as vc, \
             patch("opendance.camera.manager.PoseDetector") as mock_pd_class:
            mock_pd_class.return_value = MagicMock()
            manager = CameraManager(camera_config, pose_config)
            manager.start()
            # stop immediately to clean up worker thread
            manager.stop()

        vc.assert_called_once_with(2)  # device_index=2

    def test_successful_open_transitions_to_active(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        """Successful open → ACTIVE and state_changed emitted."""
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = True
        mock_capture.get.return_value = 640
        mock_capture.read.return_value = (False, None)  # worker will fail but that's OK

        state_changes: list[tuple[CameraState, str]] = []

        with patch("opendance.camera.manager.cv2.VideoCapture", return_value=mock_capture), \
             patch("opendance.camera.manager.PoseDetector") as mock_pd_class:
            mock_pd_class.return_value = MagicMock()
            manager = CameraManager(camera_config, pose_config)
            manager.state_changed.connect(lambda s, m: state_changes.append((s, m)))
            manager.start()

            assert manager.state == CameraState.ACTIVE
            assert (CameraState.ACTIVE, "") in state_changes

            manager.stop()

    def test_failed_open_transitions_to_error(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        """Failed VideoCapture.isOpened() → ERROR state with message."""
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = False

        state_changes: list[tuple[CameraState, str]] = []

        with patch("opendance.camera.manager.cv2.VideoCapture", return_value=mock_capture), \
             patch("opendance.camera.manager.PoseDetector") as mock_pd_class:
            mock_pd_class.return_value = MagicMock()
            manager = CameraManager(camera_config, pose_config)
            manager.state_changed.connect(lambda s, m: state_changes.append((s, m)))
            manager.start()

        assert manager.state == CameraState.ERROR
        assert "Could not open camera" in manager.error_message
        assert any(s == CameraState.ERROR for s, _ in state_changes)

    def test_missing_model_transitions_to_error(
        self, qapp: QApplication, camera_config: CameraConfig
    ) -> None:
        """Missing model file → ERROR state."""
        bad_pose_config = PoseConfig(model_path="nonexistent/model.task")
        manager = CameraManager(camera_config, bad_pose_config)
        manager.start()

        assert manager.state == CameraState.ERROR
        assert "not found" in manager.error_message.lower()


class TestCameraManagerStop:
    """Property 3: Stop from any state → INACTIVE with cleanup."""

    def _make_active_manager(
        self,
        qapp: QApplication,
        camera_config: CameraConfig,
        pose_config: PoseConfig,
    ) -> tuple[CameraManager, MagicMock, MagicMock]:
        """Helper: create a CameraManager in ACTIVE state with mocks."""
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = True
        mock_capture.get.return_value = 640
        mock_capture.read.return_value = (False, None)

        mock_pd = MagicMock()

        with patch("opendance.camera.manager.cv2.VideoCapture", return_value=mock_capture), \
             patch("opendance.camera.manager.PoseDetector", return_value=mock_pd):
            manager = CameraManager(camera_config, pose_config)
            manager.start()

        return manager, mock_capture, mock_pd

    def test_stop_from_active_transitions_to_inactive(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        manager, mock_capture, mock_pd = self._make_active_manager(
            qapp, camera_config, pose_config
        )
        assert manager.state == CameraState.ACTIVE
        manager.stop()
        assert manager.state == CameraState.INACTIVE

    def test_stop_releases_video_capture(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        manager, mock_capture, mock_pd = self._make_active_manager(
            qapp, camera_config, pose_config
        )
        manager.stop()
        mock_capture.release.assert_called_once()

    def test_stop_closes_pose_detector(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        manager, mock_capture, mock_pd = self._make_active_manager(
            qapp, camera_config, pose_config
        )
        manager.stop()
        mock_pd.close.assert_called_once()

    def test_stop_terminates_frame_worker(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        manager, mock_capture, mock_pd = self._make_active_manager(
            qapp, camera_config, pose_config
        )
        manager.stop()
        assert manager.frame_worker is None

    def test_stop_from_inactive_is_idempotent(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        """stop() on INACTIVE does not crash."""
        manager = CameraManager(camera_config, pose_config)
        assert manager.state == CameraState.INACTIVE
        manager.stop()  # Should not raise
        assert manager.state == CameraState.INACTIVE

    def test_stop_from_error_transitions_to_inactive(
        self, qapp: QApplication, camera_config: CameraConfig
    ) -> None:
        """stop() from ERROR → INACTIVE."""
        bad_pose_config = PoseConfig(model_path="nonexistent/model.task")
        manager = CameraManager(camera_config, bad_pose_config)
        manager.start()  # Will fail → ERROR
        assert manager.state == CameraState.ERROR
        manager.stop()
        assert manager.state == CameraState.INACTIVE

    def test_stop_from_paused_transitions_to_inactive(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        """stop() from PAUSED → INACTIVE."""
        manager, mock_capture, mock_pd = self._make_active_manager(
            qapp, camera_config, pose_config
        )
        manager.pause()
        assert manager.state == CameraState.PAUSED
        manager.stop()
        assert manager.state == CameraState.INACTIVE


class TestCameraManagerRepeatedCycles:
    """Property 11: Repeated start/stop cycles do not leak resources."""

    def test_repeated_start_stop_no_resource_leak(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        """N start/stop cycles result in exactly N release() calls and 0 live threads."""
        n_cycles = 5
        mock_captures: list[MagicMock] = []

        def make_capture(device_index: int) -> MagicMock:
            mc = MagicMock()
            mc.isOpened.return_value = True
            mc.get.return_value = 640
            mc.read.return_value = (False, None)
            mock_captures.append(mc)
            return mc

        with patch(
            "opendance.camera.manager.cv2.VideoCapture", side_effect=make_capture
        ), patch("opendance.camera.manager.PoseDetector") as mock_pd_class:
            mock_pd_class.return_value = MagicMock()
            manager = CameraManager(camera_config, pose_config)

            for _ in range(n_cycles):
                manager.start()
                assert manager.state == CameraState.ACTIVE
                manager.stop()
                assert manager.state == CameraState.INACTIVE

        # Exactly N captures were created and each was released
        assert len(mock_captures) == n_cycles
        for mc in mock_captures:
            mc.release.assert_called_once()

        # No frame worker alive
        assert manager.frame_worker is None

    def test_double_stop_is_safe(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        """Calling stop() twice doesn't crash or double-release."""
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = True
        mock_capture.get.return_value = 640
        mock_capture.read.return_value = (False, None)

        with patch("opendance.camera.manager.cv2.VideoCapture", return_value=mock_capture), \
             patch("opendance.camera.manager.PoseDetector") as mock_pd_class:
            mock_pd_class.return_value = MagicMock()
            manager = CameraManager(camera_config, pose_config)
            manager.start()
            manager.stop()
            manager.stop()  # Second stop should be safe

        assert manager.state == CameraState.INACTIVE
        # release called only once because second stop has no capture
        mock_capture.release.assert_called_once()


class TestCameraManagerPauseResume:
    """Test pause/resume behavior."""

    def test_pause_from_active(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = True
        mock_capture.get.return_value = 640
        mock_capture.read.return_value = (False, None)

        with patch("opendance.camera.manager.cv2.VideoCapture", return_value=mock_capture), \
             patch("opendance.camera.manager.PoseDetector") as mock_pd_class:
            mock_pd_class.return_value = MagicMock()
            manager = CameraManager(camera_config, pose_config)
            manager.start()
            manager.pause()
            assert manager.state == CameraState.PAUSED
            manager.stop()

    def test_resume_from_paused(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = True
        mock_capture.get.return_value = 640
        mock_capture.read.return_value = (False, None)

        with patch("opendance.camera.manager.cv2.VideoCapture", return_value=mock_capture), \
             patch("opendance.camera.manager.PoseDetector") as mock_pd_class:
            mock_pd_class.return_value = MagicMock()
            manager = CameraManager(camera_config, pose_config)
            manager.start()
            manager.pause()
            manager.resume()
            assert manager.state == CameraState.ACTIVE
            manager.stop()


class TestCameraManagerRestart:
    """Restart / device-change behavior (practice-io-controls task 3.2).

    Requirements 1.1, 1.3, 2.1, 2.3.
    """

    def test_restart_with_new_index_releases_and_reopens(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        """restart(new_index) releases the current resources and re-opens on the
        new index: device_index reflects it, state is ACTIVE, and a new capture
        and frame worker were created (Requirements 1.1, 2.1)."""
        mock_captures: list[MagicMock] = []

        def make_capture(device_index: int) -> MagicMock:
            mc = MagicMock()
            mc.isOpened.return_value = True
            mc.get.return_value = 640
            mc.read.return_value = (False, None)
            mock_captures.append(mc)
            return mc

        with patch(
            "opendance.camera.manager.cv2.VideoCapture", side_effect=make_capture
        ) as vc, patch("opendance.camera.manager.PoseDetector") as mock_pd_class:
            mock_pd_class.return_value = MagicMock()
            manager = CameraManager(camera_config, pose_config)
            manager.start()
            assert manager.state == CameraState.ACTIVE
            first_worker = manager.frame_worker

            manager.restart(3)

            assert manager.device_index == 3
            assert manager.state == CameraState.ACTIVE
            # A new capture was opened on the new index.
            assert vc.call_args_list[-1].args == (3,)
            assert len(mock_captures) == 2
            # The original capture was released during restart.
            mock_captures[0].release.assert_called_once()
            # A fresh frame worker was created.
            assert manager.frame_worker is not None
            assert manager.frame_worker is not first_worker

            manager.stop()

    def test_restart_without_arg_reuses_current_index(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        """restart() with no argument keeps the current device index
        (Requirement 1.1)."""
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = True
        mock_capture.get.return_value = 640
        mock_capture.read.return_value = (False, None)

        with patch(
            "opendance.camera.manager.cv2.VideoCapture", return_value=mock_capture
        ) as vc, patch("opendance.camera.manager.PoseDetector") as mock_pd_class:
            mock_pd_class.return_value = MagicMock()
            manager = CameraManager(camera_config, pose_config)
            manager.start()
            assert manager.device_index == 2

            manager.restart()

            assert manager.device_index == 2
            assert manager.state == CameraState.ACTIVE
            # Every open used the configured index (2).
            for call in vc.call_args_list:
                assert call.args == (2,)

            manager.stop()

    def test_device_index_reflects_configured_then_new_index(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        """device_index reports the configured index initially and the new index
        after a device change (Requirement 2.1)."""
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = True
        mock_capture.get.return_value = 640
        mock_capture.read.return_value = (False, None)

        with patch(
            "opendance.camera.manager.cv2.VideoCapture", return_value=mock_capture
        ), patch("opendance.camera.manager.PoseDetector") as mock_pd_class:
            mock_pd_class.return_value = MagicMock()
            manager = CameraManager(camera_config, pose_config)
            # Reflects configured index before any start.
            assert manager.device_index == 2

            manager.start()
            assert manager.device_index == 2

            manager.restart(5)
            assert manager.device_index == 5

            manager.stop()

    def test_failed_open_on_restart_transitions_to_error(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        """A failed open during restart → ERROR via state_changed, and the
        manager remains usable (no exception) (Requirements 1.3, 2.3)."""
        open_flags = iter([True, False])  # first start ok, restart fails

        def make_capture(device_index: int) -> MagicMock:
            mc = MagicMock()
            mc.isOpened.return_value = next(open_flags)
            mc.get.return_value = 640
            mc.read.return_value = (False, None)
            return mc

        state_changes: list[tuple[CameraState, str]] = []

        with patch(
            "opendance.camera.manager.cv2.VideoCapture", side_effect=make_capture
        ), patch("opendance.camera.manager.PoseDetector") as mock_pd_class:
            mock_pd_class.return_value = MagicMock()
            manager = CameraManager(camera_config, pose_config)
            manager.start()
            assert manager.state == CameraState.ACTIVE

            manager.state_changed.connect(
                lambda s, m: state_changes.append((s, m))
            )
            manager.restart(4)

            assert manager.device_index == 4
            assert manager.state == CameraState.ERROR
            assert "Could not open camera" in manager.error_message
            assert any(s == CameraState.ERROR for s, _ in state_changes)

            # Manager remains usable: a subsequent stop is safe.
            manager.stop()
            assert manager.state == CameraState.INACTIVE

    def test_restart_emits_active_state_changed(
        self, qapp: QApplication, camera_config: CameraConfig, pose_config: PoseConfig
    ) -> None:
        """A successful restart emits state_changed(ACTIVE) (Requirement 1.1)."""
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = True
        mock_capture.get.return_value = 640
        mock_capture.read.return_value = (False, None)

        with patch(
            "opendance.camera.manager.cv2.VideoCapture", return_value=mock_capture
        ), patch("opendance.camera.manager.PoseDetector") as mock_pd_class:
            mock_pd_class.return_value = MagicMock()
            manager = CameraManager(camera_config, pose_config)
            manager.start()

            state_changes: list[tuple[CameraState, str]] = []
            manager.state_changed.connect(
                lambda s, m: state_changes.append((s, m))
            )
            manager.restart(1)

            assert (CameraState.ACTIVE, "") in state_changes

            manager.stop()
