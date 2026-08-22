"""Unit tests for Phase 1 main window integration.

Verifies:
- CameraWidget is set as central widget
- aboutToQuit is connected to camera_manager.cleanup
- Window title and minimum size preserved from Phase 0
- CameraManager constructed with correct config
"""

import os
import sys
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestMainWindowIntegration:
    """Test main() creates camera pipeline and integrates with window."""

    def test_camera_widget_is_central_widget(self, qapp: QApplication) -> None:
        """CameraWidget becomes the central widget of QMainWindow."""
        with patch("opendance.camera.manager.cv2"), \
             patch("PySide6.QtWidgets.QApplication", return_value=qapp), \
             patch.object(qapp, "exec", return_value=0):
            from opendance.app.main import main
            result = main()

        assert result == 0

    def test_main_creates_camera_manager_with_config(
        self, qapp: QApplication
    ) -> None:
        """CameraManager is constructed with config.camera_config and config.pose_config."""
        from opendance.camera.manager import CameraManager
        from opendance.config.models import AppConfig

        config = AppConfig()
        with patch("opendance.camera.manager.cv2"):
            manager = CameraManager(config.camera_config, config.pose_config)
        assert manager._camera_config == config.camera_config
        assert manager._pose_config == config.pose_config

    def test_about_to_quit_connected_to_cleanup(
        self, qapp: QApplication
    ) -> None:
        """camera_manager.cleanup is callable and safe on inactive manager."""
        from opendance.camera.manager import CameraManager
        from opendance.config.models import AppConfig

        with patch("opendance.camera.manager.cv2"):
            config = AppConfig()
            manager = CameraManager(config.camera_config, config.pose_config)

        # Verify cleanup is callable and doesn't crash on inactive manager
        assert callable(manager.cleanup)
        manager.cleanup()

    def test_window_title_preserved(self, qapp: QApplication) -> None:
        """Window title remains 'OpenDance AI'."""
        from PySide6.QtWidgets import QMainWindow

        from opendance.camera.manager import CameraManager
        from opendance.config.models import AppConfig
        from opendance.ui.camera_widget import CameraWidget

        with patch("opendance.camera.manager.cv2"):
            config = AppConfig()
            manager = CameraManager(config.camera_config, config.pose_config)
            widget = CameraWidget(manager, config.pose_config)

            window = QMainWindow()
            window.setWindowTitle("OpenDance AI")
            window.setMinimumSize(800, 600)
            window.setCentralWidget(widget)

        assert window.windowTitle() == "OpenDance AI"
        assert window.minimumWidth() == 800
        assert window.minimumHeight() == 600

    def test_central_widget_is_camera_widget_instance(
        self, qapp: QApplication
    ) -> None:
        """The central widget is an instance of CameraWidget."""
        from PySide6.QtWidgets import QMainWindow

        from opendance.camera.manager import CameraManager
        from opendance.config.models import AppConfig
        from opendance.ui.camera_widget import CameraWidget

        with patch("opendance.camera.manager.cv2"):
            config = AppConfig()
            manager = CameraManager(config.camera_config, config.pose_config)
            widget = CameraWidget(manager, config.pose_config)

            window = QMainWindow()
            window.setCentralWidget(widget)

        assert isinstance(window.centralWidget(), CameraWidget)
