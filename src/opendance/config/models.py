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
class AppConfig:
    """Top-level application configuration.

    Composed of scoring thresholds and scoring weights.
    Immutable after construction — create a new instance for changes.
    """

    scoring_thresholds: ScoringThresholds = field(default_factory=ScoringThresholds)
    scoring_weights: ScoringWeights = field(default_factory=ScoringWeights)
