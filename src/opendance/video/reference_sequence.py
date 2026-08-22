"""Reference video analysis result data structures."""

from dataclasses import dataclass

from opendance.motion.motion_result import MotionFeatures
from opendance.motion.normalized_pose import NormalizedPose


@dataclass(frozen=True)
class VideoMetadata:
    """Reference video metadata extracted during analysis."""

    file_path: str
    total_frames: int
    fps: float
    duration_seconds: float
    width: int
    height: int


@dataclass(frozen=True)
class ReferenceSequence:
    """Complete analysis result for a reference video.

    Attributes:
        metadata: Video file metadata.
        poses: One NormalizedPose per sampled frame (None if no pose detected).
        motion_features: One MotionFeatures per frame (None for unavailable).
        joint_angles: One angle dict per frame (None for unavailable).
    """

    metadata: VideoMetadata
    poses: tuple[NormalizedPose | None, ...]
    motion_features: tuple[MotionFeatures | None, ...]
    joint_angles: tuple[dict[str, float | None] | None, ...]
