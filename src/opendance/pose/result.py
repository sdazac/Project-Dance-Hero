"""Pose detection result data structures for OpenDance AI."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Landmark:
    """Single landmark with image-space coordinates and metadata.

    Attributes:
        x: Normalized x coordinate [0.0, 1.0] (image-space).
        y: Normalized y coordinate [0.0, 1.0] (image-space).
        z: Normalized z coordinate (depth relative to hip midpoint).
        visibility: Likelihood the landmark is visible in the image [0.0, 1.0].
        presence: Confidence that the landmark exists on the person [0.0, 1.0].
    """

    x: float
    y: float
    z: float
    visibility: float
    presence: float


@dataclass(frozen=True)
class WorldLandmark:
    """Single landmark in real-world 3D coordinates (meters, hip-centered).

    Attributes:
        x: X position in meters.
        y: Y position in meters.
        z: Z position in meters.
        visibility: Same as Landmark.visibility.
        presence: Same as Landmark.presence.
    """

    x: float
    y: float
    z: float
    visibility: float
    presence: float


@dataclass(frozen=True)
class PoseResult:
    """Structured output of a single pose detection.

    Attributes:
        landmarks: Normalized image-space landmarks (33 for full body).
            Empty tuple if no pose detected.
        world_landmarks: World-space landmarks in meters (33 for full body).
            Empty tuple if no pose detected or world data unavailable.
        timestamp_ms: Frame timestamp in milliseconds.
    """

    landmarks: tuple[Landmark, ...] = field(default_factory=tuple)
    world_landmarks: tuple[WorldLandmark, ...] = field(default_factory=tuple)
    timestamp_ms: int = 0

    @property
    def is_empty(self) -> bool:
        """True if no pose was detected."""
        return len(self.landmarks) == 0

    @staticmethod
    def empty(timestamp_ms: int = 0) -> "PoseResult":
        """Factory for an empty result (no detection)."""
        return PoseResult(landmarks=(), world_landmarks=(), timestamp_ms=timestamp_ms)
