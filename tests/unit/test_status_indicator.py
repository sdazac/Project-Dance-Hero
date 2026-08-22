"""Unit tests for StatusIndicator widget."""

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from opendance.camera.state import CameraState
from opendance.ui.status_indicator import StatusIndicator


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestStatusIndicatorMessages:
    """Test each CameraState maps to the correct message."""

    def test_initial_state_shows_inactive(self, qapp: QApplication) -> None:
        indicator = StatusIndicator()
        assert indicator.text() == "Camera not running"

    def test_active_state(self, qapp: QApplication) -> None:
        indicator = StatusIndicator()
        indicator.update_state(CameraState.ACTIVE)
        assert indicator.text() == "Camera active"

    def test_inactive_state(self, qapp: QApplication) -> None:
        indicator = StatusIndicator()
        indicator.update_state(CameraState.INACTIVE)
        assert indicator.text() == "Camera not running"

    def test_paused_state(self, qapp: QApplication) -> None:
        indicator = StatusIndicator()
        indicator.update_state(CameraState.PAUSED)
        assert indicator.text() == "Camera paused"

    def test_error_state_uses_provided_message(self, qapp: QApplication) -> None:
        indicator = StatusIndicator()
        indicator.update_state(CameraState.ERROR, "No camera found")
        assert indicator.text() == "No camera found"

    def test_error_state_default_message(self, qapp: QApplication) -> None:
        indicator = StatusIndicator()
        indicator.update_state(CameraState.ERROR, "")
        assert indicator.text() == "Camera error"

    def test_error_state_custom_message(self, qapp: QApplication) -> None:
        indicator = StatusIndicator()
        indicator.update_state(CameraState.ERROR, "Camera disconnected")
        assert indicator.text() == "Camera disconnected"
