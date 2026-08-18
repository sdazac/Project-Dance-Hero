"""Configuration dataclass models for OpenDance AI."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScoringThresholds:
    """Scoring event thresholds (percentage boundaries).

    Each field represents the minimum percentage for that rating tier.
    Below meh_min is considered MISS.
    """

    perfect_min: float = 90.0
    great_min: float = 75.0
    ok_min: float = 50.0
    meh_min: float = 30.0


@dataclass(frozen=True)
class ScoringWeights:
    """Weighted contribution of each similarity metric.

    Each weight represents the proportion of the final accuracy score
    attributed to that similarity dimension.
    """

    pose_similarity: float = 0.40
    angle_similarity: float = 0.25
    motion_similarity: float = 0.20
    timing_similarity: float = 0.15


@dataclass(frozen=True)
class CameraConfig:
    """Camera subsystem configuration."""

    device_index: int = 0
    resolution_width: int = 640
    resolution_height: int = 480
    consecutive_failure_threshold: int = 10


@dataclass(frozen=True)
class PoseConfig:
    """Pose detection configuration."""

    model_path: str = "assets/models/pose_landmarker.task"
    skeleton_visibility_threshold: float = 0.5


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration.

    Composed of scoring, camera, and pose configuration sections.
    Immutable after construction — create a new instance for changes.
    """

    scoring_thresholds: ScoringThresholds = field(default_factory=ScoringThresholds)
    scoring_weights: ScoringWeights = field(default_factory=ScoringWeights)
    camera_config: CameraConfig = field(default_factory=CameraConfig)
    pose_config: PoseConfig = field(default_factory=PoseConfig)
