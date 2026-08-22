"""Camera status indicator widget for OpenDance AI."""

from PySide6.QtWidgets import QLabel

from opendance.camera.state import CameraState


class StatusIndicator(QLabel):
    """Displays human-readable camera status.

    Shows predefined messages for standard states and dynamic error text
    for the ERROR state.
    """

    _STATE_MESSAGES: dict[CameraState, str] = {
        CameraState.INACTIVE: "Camera not running",
        CameraState.ACTIVE: "Camera active",
        CameraState.PAUSED: "Camera paused",
        CameraState.ERROR: "",  # Uses dynamic error message
    }

    def __init__(self, parent: "QLabel | None" = None) -> None:
        super().__init__(parent)
        self.setText(self._STATE_MESSAGES[CameraState.INACTIVE])

    def update_state(self, state: CameraState, error_message: str = "") -> None:
        """Update displayed text based on camera state.

        Args:
            state: The current CameraState.
            error_message: Error description (used only when state is ERROR).
        """
        if state == CameraState.ERROR:
            self.setText(error_message or "Camera error")
        else:
            self.setText(self._STATE_MESSAGES.get(state, "Unknown state"))
