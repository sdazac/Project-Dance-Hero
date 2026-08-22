"""Entry point for the Practice Mode (Full AV Playback & Arcade HUD)."""

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "src"))

from PySide6.QtWidgets import QApplication, QMainWindow  # noqa: E402

from opendance.camera.manager import CameraManager  # noqa: E402
from opendance.config.models import AppConfig  # noqa: E402
from opendance.ui.practice_window import PracticeWindow  # noqa: E402


def main():
    app = QApplication(sys.argv)

    config = AppConfig()
    manager = CameraManager(config.camera_config, config.pose_config)

    window = QMainWindow()
    window.setWindowTitle("ModDance Hero - Full Arcade Mode")

    # Inyectamos TODA la configuración al PracticeWindow
    widget = PracticeWindow(manager, config)
    window.setCentralWidget(widget)

    window.resize(1280, 800)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
