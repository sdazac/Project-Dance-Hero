"""Unit tests for CameraWidget.

Property 9: Frame display preserves aspect ratio with correct color conversion.
Property 10: UI control state reflects Camera_State.

Tests use mocked CameraManager — no camera hardware required.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from opendance.camera.state import CameraState
from opendance.config.models import CameraConfig, PoseConfig
from opendance.pose.result import PoseResult
from opendance.ui.camera_widget import CameraWidget


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture()
def camera_widget(qapp: QApplication) -> CameraWidget:
    """Create a CameraWidget with a mocked CameraManager."""
    mock_manager = MagicMock()
    mock_manager.state = CameraState.INACTIVE
    mock_manager.state_changed = MagicMock()
    mock_manager.state_changed.connect = MagicMock()
    mock_manager.frame_worker = None
    pose_config = PoseConfig()

    # We need a real CameraManager for signal connection, so use a minimal approach
    from opendance.camera.manager import CameraManager

    with patch("opendance.camera.manager.cv2"):
        manager = CameraManager(CameraConfig(), PoseConfig())

    widget = CameraWidget(manager, pose_config)
    return widget


class TestControlState:
    """Property 10: UI control state reflects Camera_State."""

    def test_initial_start_enabled_stop_disabled(
        self, qapp: QApplication
    ) -> None:
        """Initially: Start enabled, Stop disabled."""
        from opendance.camera.manager import CameraManager

        with patch("opendance.camera.manager.cv2"):
            manager = CameraManager(CameraConfig(), PoseConfig())
        widget = CameraWidget(manager, PoseConfig())

        assert widget.start_button.isEnabled()
        assert not widget.stop_button.isEnabled()

    def test_active_state_disables_start_enables_stop(
        self, qapp: QApplication
    ) -> None:
        """ACTIVE: Start disabled, Stop enabled."""
        from opendance.camera.manager import CameraManager

        with patch("opendance.camera.manager.cv2"):
            manager = CameraManager(CameraConfig(), PoseConfig())
        widget = CameraWidget(manager, PoseConfig())

        widget._on_state_changed(CameraState.ACTIVE, "")
        assert not widget.start_button.isEnabled()
        assert widget.stop_button.isEnabled()

    def test_paused_state_disables_start_enables_stop(
        self, qapp: QApplication
    ) -> None:
        """PAUSED: Start disabled, Stop enabled."""
        from opendance.camera.manager import CameraManager

        with patch("opendance.camera.manager.cv2"):
            manager = CameraManager(CameraConfig(), PoseConfig())
        widget = CameraWidget(manager, PoseConfig())

        widget._on_state_changed(CameraState.PAUSED, "")
        assert not widget.start_button.isEnabled()
        assert widget.stop_button.isEnabled()

    def test_error_state_enables_start_disables_stop(
        self, qapp: QApplication
    ) -> None:
        """ERROR: Start enabled, Stop disabled."""
        from opendance.camera.manager import CameraManager

        with patch("opendance.camera.manager.cv2"):
            manager = CameraManager(CameraConfig(), PoseConfig())
        widget = CameraWidget(manager, PoseConfig())

        widget._on_state_changed(CameraState.ERROR, "No camera found")
        assert widget.start_button.isEnabled()
        assert not widget.stop_button.isEnabled()

    def test_inactive_state_enables_start_disables_stop(
        self, qapp: QApplication
    ) -> None:
        """INACTIVE: Start enabled, Stop disabled."""
        from opendance.camera.manager import CameraManager

        with patch("opendance.camera.manager.cv2"):
            manager = CameraManager(CameraConfig(), PoseConfig())
        widget = CameraWidget(manager, PoseConfig())

        # Transition to ACTIVE then back to INACTIVE
        widget._on_state_changed(CameraState.ACTIVE, "")
        widget._on_state_changed(CameraState.INACTIVE, "")
        assert widget.start_button.isEnabled()
        assert not widget.stop_button.isEnabled()


class TestStatusDisplay:
    """Verify status indicator reflects state changes."""

    def test_error_displays_error_message(self, qapp: QApplication) -> None:
        from opendance.camera.manager import CameraManager

        with patch("opendance.camera.manager.cv2"):
            manager = CameraManager(CameraConfig(), PoseConfig())
        widget = CameraWidget(manager, PoseConfig())

        widget._on_state_changed(CameraState.ERROR, "No camera found")
        assert widget.status_indicator.text() == "No camera found"

    def test_active_displays_camera_active(self, qapp: QApplication) -> None:
        from opendance.camera.manager import CameraManager

        with patch("opendance.camera.manager.cv2"):
            manager = CameraManager(CameraConfig(), PoseConfig())
        widget = CameraWidget(manager, PoseConfig())

        widget._on_state_changed(CameraState.ACTIVE, "")
        assert widget.status_indicator.text() == "Camera active"


class TestFrameDisplay:
    """Property 9: Frame display and conversion."""

    def test_inactive_shows_placeholder_text(self, qapp: QApplication) -> None:
        """INACTIVE state shows placeholder text, no pixmap."""
        from opendance.camera.manager import CameraManager

        with patch("opendance.camera.manager.cv2"):
            manager = CameraManager(CameraConfig(), PoseConfig())
        widget = CameraWidget(manager, PoseConfig())

        widget._on_state_changed(CameraState.INACTIVE, "")
        assert widget.display_label.text() == "Camera not active"

    def test_frame_ready_updates_display(self, qapp: QApplication) -> None:
        """Receiving a frame sets a pixmap on the display label."""
        from opendance.camera.manager import CameraManager

        with patch("opendance.camera.manager.cv2"):
            manager = CameraManager(CameraConfig(), PoseConfig())
        widget = CameraWidget(manager, PoseConfig())
        widget._display.resize(640, 480)

        # Simulate frame arrival
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:, :, 2] = 255  # Red channel in BGR
        pose_result = PoseResult.empty()

        widget._on_frame_ready(frame, pose_result)

        pixmap = widget.display_label.pixmap()
        assert pixmap is not None
        assert not pixmap.isNull()

    def test_frame_preserves_aspect_ratio(self, qapp: QApplication) -> None:
        """Displayed pixmap preserves frame aspect ratio."""
        from opendance.camera.manager import CameraManager

        with patch("opendance.camera.manager.cv2"):
            manager = CameraManager(CameraConfig(), PoseConfig())
        widget = CameraWidget(manager, PoseConfig())
        widget._display.resize(400, 300)

        # 16:9 frame into 4:3 display area
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        widget._on_frame_ready(frame, PoseResult.empty())

        pixmap = widget.display_label.pixmap()
        assert pixmap is not None
        # Aspect ratio should be approximately 16:9
        ratio = pixmap.width() / max(pixmap.height(), 1)
        original_ratio = 1280 / 720
        assert abs(ratio - original_ratio) < 0.1

    def test_paused_keeps_last_frame(self, qapp: QApplication) -> None:
        """PAUSED state keeps the last displayed frame (pixmap retained)."""
        from opendance.camera.manager import CameraManager

        with patch("opendance.camera.manager.cv2"):
            manager = CameraManager(CameraConfig(), PoseConfig())
        widget = CameraWidget(manager, PoseConfig())
        widget._display.resize(640, 480)

        # Send a frame
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        widget._on_frame_ready(frame, PoseResult.empty())

        # Transition to PAUSED — pixmap should remain
        widget._on_state_changed(CameraState.PAUSED, "")
        pixmap = widget.display_label.pixmap()
        assert pixmap is not None
        assert not pixmap.isNull()
