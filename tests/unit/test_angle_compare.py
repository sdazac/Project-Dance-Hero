"""Unit tests for joint-angle comparison with circular wraparound.

Tests compute_angle_score() with various angle configurations.
"""

import pytest

from opendance.scoring.angle_compare import compute_angle_score


class TestAngleScoreIdentical:
    """Identical angles → score 100."""

    def test_identical_angles(self) -> None:
        player = {"left_elbow": 90.0, "right_elbow": -45.0}
        ref = {"left_elbow": 90.0, "right_elbow": -45.0}
        score = compute_angle_score(player, ref)
        assert score == pytest.approx(100.0)


class TestAngleScoreKnownDifference:
    """Known angular difference → expected score."""

    def test_10_degree_mean_error(self) -> None:
        """Mean error 10° with scale 1.0 → score = 90."""
        player = {"left_elbow": 100.0, "right_elbow": -35.0}
        ref = {"left_elbow": 90.0, "right_elbow": -45.0}
        score = compute_angle_score(player, ref, angle_scale=1.0)
        assert score == pytest.approx(90.0)

    def test_50_degree_mean_error(self) -> None:
        """Mean error 50° → score = 50."""
        player = {"left_elbow": 140.0}
        ref = {"left_elbow": 90.0}
        score = compute_angle_score(player, ref, angle_scale=1.0)
        assert score == pytest.approx(50.0)

    def test_100_degree_error_is_zero(self) -> None:
        """100° mean error with scale 1.0 → score = 0."""
        player = {"joint": 0.0}
        ref = {"joint": 100.0}
        score = compute_angle_score(player, ref, angle_scale=1.0)
        assert score == pytest.approx(0.0)


class TestAngleScoreWraparound:
    """Wraparound behavior at ±180 boundary."""

    def test_minus179_vs_plus179(self) -> None:
        """Angles -179° and +179° → error = 2° (not 358°)."""
        player = {"joint": -179.0}
        ref = {"joint": 179.0}
        score = compute_angle_score(player, ref, angle_scale=1.0)
        # error = min(358, 360-358) = min(358, 2) = 2 → score = 98
        assert score == pytest.approx(98.0)

    def test_minus180_vs_plus180(self) -> None:
        """Angles -180° and +180° → error = 0° (same angle)."""
        player = {"joint": -180.0}
        ref = {"joint": 180.0}
        score = compute_angle_score(player, ref, angle_scale=1.0)
        # abs_diff = 360, error = min(360, 0) = 0
        assert score == pytest.approx(100.0)

    def test_minus170_vs_plus170(self) -> None:
        """Angles -170° and +170° → error = 20°."""
        player = {"joint": -170.0}
        ref = {"joint": 170.0}
        score = compute_angle_score(player, ref, angle_scale=1.0)
        # abs_diff = 340, error = min(340, 20) = 20 → score = 80
        assert score == pytest.approx(80.0)


class TestAngleScoreMissing:
    """Missing angles excluded."""

    def test_one_none_excluded(self) -> None:
        """Joint with None on one side is excluded from mean."""
        player = {"left_elbow": 90.0, "right_elbow": None}
        ref = {"left_elbow": 90.0, "right_elbow": 45.0}
        score = compute_angle_score(player, ref)
        # Only left_elbow compared: error 0 → score 100
        assert score == pytest.approx(100.0)

    def test_all_none_returns_none(self) -> None:
        player = {"left_elbow": None, "right_elbow": None}
        ref = {"left_elbow": 90.0, "right_elbow": 45.0}
        score = compute_angle_score(player, ref)
        assert score is None

    def test_ref_missing_joint(self) -> None:
        """Reference missing a joint that player has → excluded."""
        player = {"left_elbow": 90.0, "extra_joint": 45.0}
        ref = {"left_elbow": 90.0}
        score = compute_angle_score(player, ref)
        # Only left_elbow matches → error 0 → score 100
        assert score == pytest.approx(100.0)


class TestAngleScoreConfig:
    """Configured angle_scale respected."""

    def test_custom_scale(self) -> None:
        """Scale 0.5: 100° error → score = 100 - 50 = 50."""
        player = {"joint": 0.0}
        ref = {"joint": 100.0}
        score = compute_angle_score(player, ref, angle_scale=0.5)
        assert score == pytest.approx(50.0)


class TestAngleScoreBounded:
    """Score always in [0, 100]."""

    def test_never_negative(self) -> None:
        player = {"joint": 0.0}
        ref = {"joint": 180.0}  # max possible error
        score = compute_angle_score(player, ref, angle_scale=1.0)
        assert score is not None
        assert score >= 0.0

    def test_never_above_100(self) -> None:
        player = {"joint": 50.0}
        ref = {"joint": 50.0}
        score = compute_angle_score(player, ref)
        assert score is not None
        assert score <= 100.0


class TestAngleScoreDeterminism:
    """Deterministic repeated computation."""

    def test_same_inputs_same_output(self) -> None:
        player = {"a": 45.0, "b": -90.0, "c": 170.0}
        ref = {"a": 50.0, "b": -85.0, "c": -175.0}
        s1 = compute_angle_score(player, ref)
        s2 = compute_angle_score(player, ref)
        assert s1 == s2
