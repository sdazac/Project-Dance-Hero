"""OpenDance AI configuration system."""

from opendance.config.loader import load_config
from opendance.config.models import (
    AppConfig,
    CameraConfig,
    ComparisonConfig,
    MotionConfig,
    NormalizationConfig,
    PoseConfig,
    ReferenceConfig,
    ScoringThresholds,
    ScoringWeights,
)

__all__ = [
    "load_config",
    "AppConfig",
    "CameraConfig",
    "ComparisonConfig",
    "MotionConfig",
    "NormalizationConfig",
    "PoseConfig",
    "ReferenceConfig",
    "ScoringThresholds",
    "ScoringWeights",
]
