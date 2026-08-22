"""Application entry point for OpenDance AI.

Initializes logging, configuration, and the PySide6 GUI in strict order:
1. Logging System
2. Configuration System
3. PySide6 QApplication
4. Main Window with Camera Pipeline
"""

import sys

from PySide6.QtWidgets import QApplication, QMainWindow


def main() -> int:
    """Application entry point. Returns exit code.

    Initialization order:
    1. setup_logging() — if it raises, write to stderr and continue with defaults
    2. load_config() — if it raises, log error and continue with default AppConfig()
    3. Create QApplication
    4. Create CameraManager with camera+pose config
    5. Create CameraWidget as central widget
    6. Connect aboutToQuit → cleanup
    7. Start Qt event loop
    """
    # 1. Initialize logging system
    try:
        from opendance.logging_setup import setup_logging
        setup_logging()
    except Exception as exc:
        print(f"Failed to initialize logging: {exc}", file=sys.stderr)

    # 2. Initialize configuration system
    try:
        from opendance.config import load_config
        config = load_config()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error(
            "Configuration initialization failed: %s. Using defaults.", exc
        )
        from opendance.config.models import AppConfig
        config = AppConfig()

    # 3. Create QApplication and main window
    try:
        app = QApplication(sys.argv)

        window = QMainWindow()
        window.setWindowTitle("OpenDance AI")
        window.setMinimumSize(800, 600)

        # 4. Create camera pipeline (Phase 1)
        from opendance.camera.manager import CameraManager
        from opendance.ui.camera_widget import CameraWidget

        camera_manager = CameraManager(config.camera_config, config.pose_config)
        camera_widget = CameraWidget(camera_manager, config.pose_config)
        window.setCentralWidget(camera_widget)

        # 5. Connect cleanup on application quit
        app.aboutToQuit.connect(camera_manager.cleanup)

        window.show()
        return app.exec()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error(
            "Unhandled exception before event loop: %s", exc, exc_info=True
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
