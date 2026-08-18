"""Camera state enumeration for OpenDance AI."""

from enum import Enum, auto


class CameraState(Enum):
    """Operational states for the camera subsystem."""

    INACTIVE = auto()
    ACTIVE = auto()
    PAUSED = auto()
    ERROR = auto()
