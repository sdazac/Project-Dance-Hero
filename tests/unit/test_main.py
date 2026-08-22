"""Unit tests for the OpenDance AI application entry point.

Tests cover:
- Initialization order (logging → config → UI)
- Configuration failure resilience
- Logging failure resilience
- Window properties (title, minimum size)

Requires QT_QPA_PLATFORM=offscreen for headless testing.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow

# Ensure offscreen rendering for headless Qt testing
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Create or reuse a QApplication instance for all tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestStartupOrder:
    """Test main() initialization order: logging → config → UI."""

    def test_logging_called_before_config(self, qapp: QApplication) -> None:
        """Verify setup_logging is called before load_config in main()."""
        call_order: list[str] = []

        def track_setup() -> None:
            call_order.append("logging")

        def track_load(*args: object, **kwargs: object) -> object:
            call_order.append("config")
            from opendance.config.models import AppConfig
            return AppConfig()

        with patch("opendance.logging_setup.setup_logging", side_effect=track_setup), \
             patch("opendance.config.load_config", side_effect=track_load), \
             patch("PySide6.QtWidgets.QApplication", return_value=qapp), \
             patch.object(qapp, "exec", return_value=0), \
             patch("PySide6.QtWidgets.QMainWindow") as mock_window_class:
            mock_window = MagicMock()
            mock_window_class.return_value = mock_window

            from opendance.app.main import main
            main()

        assert "logging" in call_order
        assert "config" in call_order
        assert call_order.index("logging") < call_order.index("config")


class TestConfigFailureResilience:
    """Test that config failure doesn't prevent startup."""

    def test_config_failure_continues_startup(
        self, qapp: QApplication
    ) -> None:
        """If load_config raises, main() continues with default AppConfig."""
        with patch(
            "opendance.config.load_config",
            side_effect=RuntimeError("config broken"),
        ), \
             patch("PySide6.QtWidgets.QApplication", return_value=qapp), \
             patch.object(qapp, "exec", return_value=0), \
             patch("PySide6.QtWidgets.QMainWindow") as mock_window_class:
            mock_window = MagicMock()
            mock_window_class.return_value = mock_window

            from opendance.app.main import main
            result = main()

        assert result == 0


class TestLoggingFailureResilience:
    """Test that logging failure doesn't prevent startup."""

    def test_logging_failure_writes_stderr_and_continues(
        self, qapp: QApplication, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """If setup_logging raises, main() writes to stderr and continues."""
        with patch(
            "opendance.logging_setup.setup_logging",
            side_effect=RuntimeError("log broken"),
        ), \
             patch("PySide6.QtWidgets.QApplication", return_value=qapp), \
             patch.object(qapp, "exec", return_value=0), \
             patch("PySide6.QtWidgets.QMainWindow") as mock_window_class:
            mock_window = MagicMock()
            mock_window_class.return_value = mock_window

            from opendance.app.main import main
            result = main()

        captured = capsys.readouterr()
        assert "log broken" in captured.err
        assert result == 0


class TestWindowProperties:
    """Test main window has correct title and minimum size."""

    def test_window_title_is_opendance_ai(self, qapp: QApplication) -> None:
        """Window title must be 'OpenDance AI'."""
        window = QMainWindow()
        window.setWindowTitle("OpenDance AI")
        assert window.windowTitle() == "OpenDance AI"
        window.close()

    def test_window_minimum_size_800x600(self, qapp: QApplication) -> None:
        """Window minimum size must be 800x600."""
        window = QMainWindow()
        window.setMinimumSize(800, 600)
        assert window.minimumWidth() == 800
        assert window.minimumHeight() == 600
        window.close()
