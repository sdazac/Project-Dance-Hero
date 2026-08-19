"""NormalizedPose data model for body-relative pose representation."""

from dataclasses import dataclass

from opendance.motion.landmarks import NUM_LANDMARKS


@dataclass(frozen=True)
class NormalizedPose:
    """Body-relative pose after translation and scale removal.

    Attributes:
        timestamp_ms: Authoritative frame timestamp from PoseResult.
        landmarks_2d: 33-element tuple of (x, y, z) body-normalized coords or None.
            None entries indicate unreliable landmarks (visibility < threshold).
        landmarks_3d: 33-element tuple of (x, y, z) body-normalized world coords or None.
            Entire field is None if world landmarks were unavailable.
        visibilities: 33-element tuple of original Landmark.visibility values.
        presences: 33-element tuple of original Landmark.presence values.
        body_center: (x, y, z) tuple — the computed center before normalization.
        body_scale: float — the Euclidean scale divisor used.
        valid: bool — False if normalization could not be performed
            (insufficient torso data or body_scale below min_body_scale).
    """

    timestamp_ms: int
    landmarks_2d: tuple[tuple[float, float, float] | None, ...]
    landmarks_3d: tuple[tuple[float, float, float] | None, ...] | None
    visibilities: tuple[float, ...]
    presences: tuple[float, ...]
    body_center: tuple[float, float, float]
    body_scale: float
    valid: bool

    @staticmethod
    def invalid(timestamp_ms: int = 0) -> "NormalizedPose":
        """Factory for a failed normalization result (valid=False)."""
        return NormalizedPose(
            timestamp_ms=timestamp_ms,
            landmarks_2d=tuple(None for _ in range(NUM_LANDMARKS)),
            landmarks_3d=None,
            visibilities=tuple(0.0 for _ in range(NUM_LANDMARKS)),
            presences=tuple(0.0 for _ in range(NUM_LANDMARKS)),
            body_center=(0.0, 0.0, 0.0),
            body_scale=0.0,
            valid=False,
        )
