"""Motion feature data structures for OpenDance AI."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LandmarkMotion:
    """Per-landmark motion data for a single frame.

    All values are in body-normalized units/sec (velocity) or units/sec² (acceleration).
    None indicates the value could not be computed (missing landmark, zero dt, etc.).
    """

    velocity_x: float | None
    velocity_y: float | None
    velocity_z: float | None
    speed: float | None
    acceleration: float | None
    direction_x: float | None
    direction_y: float | None
    direction_z: float | None


@dataclass(frozen=True)
class MotionFeatures:
    """Motion features for one frame in a sequence."""

    landmark_motions: tuple[LandmarkMotion | None, ...]  # 33 entries
    timestamp_ms: int
    dt_seconds: float

    @property
    def is_empty(self) -> bool:
        """True if all landmark motions are None."""
        return all(lm is None for lm in self.landmark_motions)
