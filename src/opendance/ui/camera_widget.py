"""Camera display widget with controls and status for OpenDance AI."""

import cv2
import numpy as np
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from opendance.camera.manager import CameraManager
from opendance.camera.state import CameraState
from opendance.config.models import PoseConfig
from opendance.pose.result import PoseResult
from opendance.ui.skeleton_renderer import render_skeleton
from opendance.ui.status_indicator import StatusIndicator


class CameraWidget(QWidget):
    """Main camera display widget with controls and status.

    Layout:
    ┌─────────────────────────────┐
    │      Camera Feed (QLabel)    │
    │    (scaled, aspect ratio)    │
    ├─────────────────────────────┤
    │  [Start] [Stop]  | Status   │
    └─────────────────────────────┘
    """

    def __init__(
        self,
        camera_manager: CameraManager,
        pose_config: PoseConfig,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._camera_manager = camera_manager
        self._pose_config = pose_config

        # Display label for camera feed
        self._display = QLabel()
        self._display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._display.setText("Camera not active")
        self._display.setMinimumSize(320, 240)

        # Controls
        self._start_button = QPushButton("Start")
        self._stop_button = QPushButton("Stop")
        self._stop_button.setEnabled(False)

        # Status indicator
        self._status_indicator = StatusIndicator()

        # Layout
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self._start_button)
        controls_layout.addWidget(self._stop_button)
        controls_layout.addWidget(self._status_indicator)
        controls_layout.addStretch()

        main_layout = QVBoxLayout()
        main_layout.addWidget(self._display, stretch=1)
        main_layout.addLayout(controls_layout)
        self.setLayout(main_layout)

        # Connect signals
        self._start_button.clicked.connect(self._start_camera)
        self._stop_button.clicked.connect(self._stop_camera)
        self._camera_manager.state_changed.connect(self._on_state_changed)

    @property
    def start_button(self) -> QPushButton:
        """Access start button for testing."""
        return self._start_button

    @property
    def stop_button(self) -> QPushButton:
        """Access stop button for testing."""
        return self._stop_button

    @property
    def status_indicator(self) -> StatusIndicator:
        """Access status indicator for testing."""
        return self._status_indicator

    @property
    def display_label(self) -> QLabel:
        """Access display label for testing."""
        return self._display

    @Slot()
    def _start_camera(self) -> None:
        """Slot for Start button click."""
        self._camera_manager.start()
        # Connect frame_ready from the new worker if available
        if self._camera_manager.frame_worker is not None:
            self._camera_manager.frame_worker.frame_ready.connect(self._on_frame_ready)

    @Slot()
    def _stop_camera(self) -> None:
        """Slot for Stop button click."""
        self._camera_manager.stop()

    @Slot(object, str)
    def _on_state_changed(self, state: CameraState, error_msg: str) -> None:
        """Update controls and status indicator based on new state."""
        # Update button enabled state
        self._start_button.setEnabled(state in {CameraState.INACTIVE, CameraState.ERROR})
        self._stop_button.setEnabled(state in {CameraState.ACTIVE, CameraState.PAUSED})

        # Update status
        self._status_indicator.update_state(state, error_msg)

        # Handle display for inactive state
        if state == CameraState.INACTIVE:
            self._display.clear()
            self._display.setText("Camera not active")

    @Slot(object, object)
    def _on_frame_ready(self, frame: np.ndarray, pose_result: PoseResult) -> None:
        """Handle frame+pose from worker: render skeleton, convert, display."""
        # Render skeleton overlay on the frame (in UI thread, fast operation)
        render_skeleton(
            frame,
            pose_result,
            visibility_threshold=self._pose_config.skeleton_visibility_threshold,
        )

        # Convert BGR → RGB → QImage → QPixmap
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qimage = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage)

        # Scale to fit display area preserving aspect ratio
        scaled = pixmap.scaled(
            self._display.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._display.setPixmap(scaled)
