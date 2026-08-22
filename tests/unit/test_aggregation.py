"""Unit tests for score aggregation and event rating.

Tests aggregate_scores() and compute_event_rating() per approved spec.
"""

import pytest

from opendance.config.models import ScoringThresholds, ScoringWeights
from opendance.scoring.aggregation import aggregate_scores
from opendance.scoring.models import EventRating
from opendance.scoring.rating import compute_event_rating

DEFAULT_WEIGHTS = ScoringWeights()
DEFAULT_THRESHOLDS = ScoringThresholds()


class TestAggregationAllPresent:
    """All four scores present."""

    def test_all_100(self) -> None:
        score = aggregate_scores(100.0, 100.0, 100.0, 100.0, DEFAULT_WEIGHTS)
        assert score == pytest.approx(100.0)

    def test_all_zero(self) -> None:
        score = aggregate_scores(0.0, 0.0, 0.0, 0.0, DEFAULT_WEIGHTS)
        assert score == pytest.approx(0.0)

    def test_known_weighted_result(self) -> None:
        """pose=80, angle=90, motion=70, timing=60.
        combined = (0.40*80 + 0.25*90 + 0.20*70 + 0.15*60) / 1.0
                 = (32 + 22.5 + 14 + 9) / 1.0 = 77.5
        """
        score = aggregate_scores(80.0, 90.0, 70.0, 60.0, DEFAULT_WEIGHTS)
        assert score == pytest.approx(77.5)


class TestAggregationMissingScores:
    """Individual and multiple missing scores."""

    def test_pose_missing(self) -> None:
        """pose=None: weights renormalize over angle+motion+timing.
        (0.25*90 + 0.20*70 + 0.15*60) / (0.25+0.20+0.15)
        = (22.5 + 14 + 9) / 0.60 = 75.83...
        """
        score = aggregate_scores(None, 90.0, 70.0, 60.0, DEFAULT_WEIGHTS)
        assert score == pytest.approx(45.5 / 0.60)

    def test_motion_and_timing_missing(self) -> None:
        """Only pose and angle available.
        (0.40*80 + 0.25*90) / (0.40+0.25) = (32+22.5)/0.65 = 83.846...
        """
        score = aggregate_scores(80.0, 90.0, None, None, DEFAULT_WEIGHTS)
        assert score == pytest.approx(54.5 / 0.65)

    def test_only_pose(self) -> None:
        """Only pose score: combined = pose_score itself."""
        score = aggregate_scores(75.0, None, None, None, DEFAULT_WEIGHTS)
        assert score == pytest.approx(75.0)

    def test_all_none(self) -> None:
        score = aggregate_scores(None, None, None, None, DEFAULT_WEIGHTS)
        assert score is None


class TestAggregationBoundary:
    """Boundary scores."""

    def test_result_bounded_0(self) -> None:
        score = aggregate_scores(0.0, 0.0, 0.0, 0.0, DEFAULT_WEIGHTS)
        assert score is not None
        assert score >= 0.0

    def test_result_bounded_100(self) -> None:
        score = aggregate_scores(100.0, 100.0, 100.0, 100.0, DEFAULT_WEIGHTS)
        assert score is not None
        assert score <= 100.0


class TestAggregationDeterminism:
    """Deterministic repeated computation."""

    def test_same_input_same_output(self) -> None:
        s1 = aggregate_scores(85.0, 72.0, 90.0, 65.0, DEFAULT_WEIGHTS)
        s2 = aggregate_scores(85.0, 72.0, 90.0, 65.0, DEFAULT_WEIGHTS)
        assert s1 == s2


class TestEventRatingClassification:
    """Test threshold-based classification."""

    def test_none_is_miss(self) -> None:
        assert compute_event_rating(None, DEFAULT_THRESHOLDS) == EventRating.MISS

    def test_100_is_perfect(self) -> None:
        assert compute_event_rating(100.0, DEFAULT_THRESHOLDS) == EventRating.PERFECT

    def test_exactly_90_is_perfect(self) -> None:
        assert compute_event_rating(90.0, DEFAULT_THRESHOLDS) == EventRating.PERFECT

    def test_89_99_is_great(self) -> None:
        assert compute_event_rating(89.99, DEFAULT_THRESHOLDS) == EventRating.GREAT

    def test_exactly_75_is_great(self) -> None:
        assert compute_event_rating(75.0, DEFAULT_THRESHOLDS) == EventRating.GREAT

    def test_74_99_is_ok(self) -> None:
        assert compute_event_rating(74.99, DEFAULT_THRESHOLDS) == EventRating.OK

    def test_exactly_50_is_ok(self) -> None:
        assert compute_event_rating(50.0, DEFAULT_THRESHOLDS) == EventRating.OK

    def test_49_99_is_meh(self) -> None:
        assert compute_event_rating(49.99, DEFAULT_THRESHOLDS) == EventRating.MEH

    def test_exactly_30_is_meh(self) -> None:
        assert compute_event_rating(30.0, DEFAULT_THRESHOLDS) == EventRating.MEH

    def test_29_99_is_miss(self) -> None:
        assert compute_event_rating(29.99, DEFAULT_THRESHOLDS) == EventRating.MISS

    def test_0_is_miss(self) -> None:
        assert compute_event_rating(0.0, DEFAULT_THRESHOLDS) == EventRating.MISS


class TestEventRatingDeterminism:
    """Deterministic."""

    def test_same_input(self) -> None:
        r1 = compute_event_rating(77.5, DEFAULT_THRESHOLDS)
        r2 = compute_event_rating(77.5, DEFAULT_THRESHOLDS)
        assert r1 == r2 == EventRating.GREAT
