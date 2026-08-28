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
    max_poses: int = 1


@dataclass(frozen=True)
class NormalizationConfig:
    """Pose normalization configuration (Phase 2)."""

    enabled: bool = False
    visibility_threshold: float = 0.5
    min_body_scale: float = 0.001
    missing_data_strategy: str = "leave_none"


@dataclass(frozen=True)
class MotionConfig:
    """Motion feature extraction configuration (Phase 2)."""

    min_velocity_threshold: float = 0.01


@dataclass(frozen=True)
class ReferenceConfig:
    """Reference video analysis configuration (Phase 2)."""

    cache_directory: str = ""
    auto_cache: bool = False
    sample_fps: float = 15.0


@dataclass(frozen=True)
class ComparisonConfig:
    """Scoring comparison parameters (Phase 3)."""

    pose_scale_factor: float = 200.0
    angle_scale: float = 1.0
    timing_scale: float = 0.5
    min_valid_landmarks: int = 8
    feedback_significance_threshold: float = 0.1
    motion_speed_weight: float = 0.5
    motion_direction_weight: float = 0.5
    epsilon: float = 0.001


@dataclass(frozen=True)
class PracticeConfig:
    """Practice loop performance configuration (Phase 4).

    Controls the decoupled render/scoring rates and silhouette rendering size
    so smoothness and scoring load can be tuned independently per hardware.
    """

    render_fps: float = 30.0
    scoring_fps: float = 12.0
    silhouette_size: int = 250
    # Selectable playback speed multipliers and the initial default speed.
    playback_speeds: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5)
    default_playback_speed: float = 1.0


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration.

    Composed of scoring, camera, pose, normalization, motion, reference,
    comparison, and practice sections.
    Immutable after construction — create a new instance for changes.
    """

    scoring_thresholds: ScoringThresholds = field(default_factory=ScoringThresholds)
    scoring_weights: ScoringWeights = field(default_factory=ScoringWeights)
    camera_config: CameraConfig = field(default_factory=CameraConfig)
    pose_config: PoseConfig = field(default_factory=PoseConfig)
    normalization_config: NormalizationConfig = field(
        default_factory=NormalizationConfig
    )
    motion_config: MotionConfig = field(default_factory=MotionConfig)
    reference_config: ReferenceConfig = field(default_factory=ReferenceConfig)
    comparison_config: ComparisonConfig = field(default_factory=ComparisonConfig)
    practice_config: PracticeConfig = field(default_factory=PracticeConfig)
