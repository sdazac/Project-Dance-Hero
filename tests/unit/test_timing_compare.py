"""Unit tests for timing comparison (movement-phase alignment).

Tests compute_timing_score() — verifies phase alignment is distinct from
motion comparison. Timing measures WHETHER both are in the same movement
state, not HOW WELL their speeds/directions match.
"""

import pytest

from opendance.motion.motion_result import LandmarkMotion, MotionFeatures
from opendance.scoring.timing_compare import compute_timing_score


def _lm(speed: float = 1.0) -> LandmarkMotion:
    return LandmarkMotion(
        velocity_x=speed, velocity_y=0.0, velocity_z=0.0,
        speed=speed, acceleration=None,
        direction_x=1.0 if speed > 0 else 0.0,
        direction_y=0.0, direction_z=0.0,
    )


def _make_motion(landmarks: list[LandmarkMotion | None]) -> MotionFeatures:
    return MotionFeatures(
        landmark_motions=tuple(landmarks),
        timestamp_ms=0,
        dt_seconds=0.033,
    )


class TestTimingBothStill:
    """Both still → 100 (same phase)."""

    def test_both_below_threshold(self) -> None:
        p = _make_motion([_lm(0.005)] * 5)
        r = _make_motion([_lm(0.005)] * 5)
        score = compute_timing_score(p, r, velocity_threshold=0.01)
        assert score == pytest.approx(100.0)

    def test_both_zero_speed(self) -> None:
        p = _make_motion([_lm(0.0)] * 3)
        r = _make_motion([_lm(0.0)] * 3)
        score = compute_timing_score(p, r)
        assert score == pytest.approx(100.0)


class TestTimingBothMoving:
    """Both moving → 100 (same phase)."""

    def test_both_above_threshold(self) -> None:
        p = _make_motion([_lm(2.0)] * 5)
        r = _make_motion([_lm(3.0)] * 5)
        score = compute_timing_score(p, r, velocity_threshold=0.01)
        assert score == pytest.approx(100.0)

    def test_different_speeds_same_phase(self) -> None:
        """Speed magnitudes differ but both are moving → still 100."""
        p = _make_motion([_lm(0.5)] * 3)
        r = _make_motion([_lm(5.0)] * 3)
        score = compute_timing_score(p, r, velocity_threshold=0.01)
        assert score == pytest.approx(100.0)


class TestTimingRefMovingPlayerStill:
    """Reference moving, player still → penalty."""

    def test_ref_moving_player_still(self) -> None:
        """ref speed=0.8, player speed=0.005 (below threshold).
        penalty = 0.8 * 0.5 * 1000 = 400 → per_lm = max(0, 100-400) = 0.
        """
        p = _make_motion([_lm(0.005)])
        r = _make_motion([_lm(0.8)])
        score = compute_timing_score(p, r, timing_scale=0.5, velocity_threshold=0.01)
        assert score == pytest.approx(0.0)

    def test_small_ref_speed_small_penalty(self) -> None:
        """ref speed=0.05, player still.
        penalty = 0.05 * 0.5 * 1000 = 25 → per_lm = 75.
        """
        p = _make_motion([_lm(0.005)])
        r = _make_motion([_lm(0.05)])
        score = compute_timing_score(p, r, timing_scale=0.5, velocity_threshold=0.01)
        assert score == pytest.approx(75.0)


class TestTimingPlayerMovingRefStill:
    """Player moving, reference still → early movement penalty."""

    def test_player_moving_ref_still(self) -> None:
        """player speed=0.1, ref speed=0.005.
        penalty = 0.1 * 0.5 * 1000 = 50 → per_lm = 50.
        """
        p = _make_motion([_lm(0.1)])
        r = _make_motion([_lm(0.005)])
        score = compute_timing_score(p, r, timing_scale=0.5, velocity_threshold=0.01)
        assert score == pytest.approx(50.0)


class TestTimingScaleConfig:
    """timing_scale configuration."""

    def test_larger_scale_more_penalty(self) -> None:
        """timing_scale=1.0: penalty = 0.1 * 1.0 * 1000 = 100 → score 0."""
        p = _make_motion([_lm(0.005)])
        r = _make_motion([_lm(0.1)])
        score = compute_timing_score(p, r, timing_scale=1.0, velocity_threshold=0.01)
        assert score == pytest.approx(0.0)

    def test_smaller_scale_less_penalty(self) -> None:
        """timing_scale=0.1: penalty = 0.1 * 0.1 * 1000 = 10 → score 90."""
        p = _make_motion([_lm(0.005)])
        r = _make_motion([_lm(0.1)])
        score = compute_timing_score(p, r, timing_scale=0.1, velocity_threshold=0.01)
        assert score == pytest.approx(90.0)


class TestTimingThreshold:
    """Movement threshold semantics."""

    def test_at_threshold_is_still(self) -> None:
        """Speed exactly at threshold is NOT > threshold → still."""
        p = _make_motion([_lm(0.01)])
        r = _make_motion([_lm(0.01)])
        score = compute_timing_score(p, r, velocity_threshold=0.01)
        # Both at threshold (not >) → both still → 100
        assert score == pytest.approx(100.0)

    def test_just_above_threshold_is_moving(self) -> None:
        """Speed just above threshold → moving."""
        p = _make_motion([_lm(0.011)])
        r = _make_motion([_lm(0.011)])
        score = compute_timing_score(p, r, velocity_threshold=0.01)
        # Both moving → 100
        assert score == pytest.approx(100.0)


class TestTimingMissingData:
    """Missing data handling."""

    def test_player_motion_none(self) -> None:
        r = _make_motion([_lm(1.0)])
        score = compute_timing_score(None, r)
        assert score is None

    def test_reference_motion_none(self) -> None:
        p = _make_motion([_lm(1.0)])
        score = compute_timing_score(p, None)
        assert score is None

    def test_landmark_none_excluded(self) -> None:
        p = _make_motion([_lm(1.0), None, _lm(1.0)])
        r = _make_motion([_lm(1.0), _lm(1.0), _lm(1.0)])
        # 2 valid landmarks, both same phase → 100
        score = compute_timing_score(p, r)
        assert score == pytest.approx(100.0)

    def test_speed_none_excluded(self) -> None:
        lm_no_speed = LandmarkMotion(
            velocity_x=None, velocity_y=None, velocity_z=None,
            speed=None, acceleration=None,
            direction_x=None, direction_y=None, direction_z=None,
        )
        p = _make_motion([lm_no_speed])
        r = _make_motion([_lm(1.0)])
        score = compute_timing_score(p, r)
        assert score is None

    def test_no_valid_landmarks_returns_none(self) -> None:
        p = _make_motion([None, None])
        r = _make_motion([None, None])
        score = compute_timing_score(p, r)
        assert score is None


class TestTimingBounded:
    """Score bounded [0, 100]."""

    def test_never_negative(self) -> None:
        p = _make_motion([_lm(0.0)])
        r = _make_motion([_lm(100.0)])
        score = compute_timing_score(p, r)
        assert score is not None
        assert score >= 0.0

    def test_never_above_100(self) -> None:
        p = _make_motion([_lm(2.0)])
        r = _make_motion([_lm(2.0)])
        score = compute_timing_score(p, r)
        assert score is not None
        assert score <= 100.0


class TestTimingDeterminism:
    """Deterministic repeated computation."""

    def test_same_input_same_output(self) -> None:
        p = _make_motion([_lm(0.5), _lm(0.0), _lm(1.0)])
        r = _make_motion([_lm(0.0), _lm(0.5), _lm(1.0)])
        s1 = compute_timing_score(p, r)
        s2 = compute_timing_score(p, r)
        assert s1 == s2
