"""Unit tests for motion comparison (speed + direction).

Tests compute_motion_score() with synthetic MotionFeatures.
"""

import pytest

from opendance.motion.motion_result import LandmarkMotion, MotionFeatures
from opendance.scoring.motion_compare import compute_motion_score


def _lm(
    speed: float = 1.0,
    vx: float = 1.0, vy: float = 0.0, vz: float = 0.0,
    dx: float = 1.0, dy: float = 0.0, dz: float = 0.0,
) -> LandmarkMotion:
    return LandmarkMotion(
        velocity_x=vx, velocity_y=vy, velocity_z=vz,
        speed=speed, acceleration=None,
        direction_x=dx, direction_y=dy, direction_z=dz,
    )


def _make_motion(landmarks: list[LandmarkMotion | None]) -> MotionFeatures:
    return MotionFeatures(
        landmark_motions=tuple(landmarks),
        timestamp_ms=0,
        dt_seconds=0.033,
    )


class TestMotionScoreIdentical:
    """Identical motion → 100."""

    def test_identical_speed_and_direction(self) -> None:
        lm = _lm(speed=2.0, dx=1.0, dy=0.0, dz=0.0)
        player = _make_motion([lm] * 10)
        ref = _make_motion([lm] * 10)
        score = compute_motion_score(player, ref)
        assert score == pytest.approx(100.0)


class TestMotionScoreSpeedMismatch:
    """Known speed mismatch."""

    def test_speed_mismatch(self) -> None:
        """p_speed=2, r_speed=4 → speed_sim = 1 - 2/4 = 0.5."""
        p_lm = _lm(speed=2.0, dx=1.0, dy=0.0, dz=0.0)
        r_lm = _lm(speed=4.0, dx=1.0, dy=0.0, dz=0.0)
        player = _make_motion([p_lm])
        ref = _make_motion([r_lm])
        # speed_sim=0.5, dir_sim=1.0 (same direction)
        # per_lm = 0.5*0.5 + 1.0*0.5 = 0.75
        score = compute_motion_score(player, ref)
        assert score == pytest.approx(75.0)


class TestMotionScoreDirectionMismatch:
    """Known direction mismatch."""

    def test_perpendicular_directions(self) -> None:
        """Dot of (1,0,0) and (0,1,0) = 0 → dir_sim=0."""
        p_lm = _lm(speed=2.0, dx=1.0, dy=0.0, dz=0.0)
        r_lm = _lm(speed=2.0, dx=0.0, dy=1.0, dz=0.0)
        player = _make_motion([p_lm])
        ref = _make_motion([r_lm])
        # speed_sim=1.0, dir_sim=0.0
        # per_lm = 1.0*0.5 + 0.0*0.5 = 0.5
        score = compute_motion_score(player, ref)
        assert score == pytest.approx(50.0)

    def test_opposite_direction_zero_contribution(self) -> None:
        """Dot of (1,0,0) and (-1,0,0) = -1 → clamped to 0."""
        p_lm = _lm(speed=2.0, dx=1.0, dy=0.0, dz=0.0)
        r_lm = _lm(speed=2.0, dx=-1.0, dy=0.0, dz=0.0)
        player = _make_motion([p_lm])
        ref = _make_motion([r_lm])
        # speed_sim=1.0, dir_sim=max(0,-1)=0
        # per_lm = 1.0*0.5 + 0*0.5 = 0.5
        score = compute_motion_score(player, ref)
        assert score == pytest.approx(50.0)


class TestMotionScoreZeroSpeed:
    """Both speeds below epsilon → perfect similarity."""

    def test_both_still(self) -> None:
        p_lm = _lm(speed=0.0, dx=0.0, dy=0.0, dz=0.0)
        r_lm = _lm(speed=0.0, dx=0.0, dy=0.0, dz=0.0)
        player = _make_motion([p_lm])
        ref = _make_motion([r_lm])
        # Both below epsilon → speed_sim=1.0, direction undefined → per_lm=1.0
        score = compute_motion_score(player, ref, epsilon=0.001)
        assert score == pytest.approx(100.0)

    def test_one_moving_one_still(self) -> None:
        """One speed=0, other=2 → speed_sim = 1 - 2/2 = 0."""
        p_lm = _lm(speed=0.0, dx=0.0, dy=0.0, dz=0.0)
        r_lm = _lm(speed=2.0, dx=1.0, dy=0.0, dz=0.0)
        player = _make_motion([p_lm])
        ref = _make_motion([r_lm])
        # player speed < epsilon → direction undefined → use speed only
        # speed_sim = 1 - 2/2 = 0
        score = compute_motion_score(player, ref, epsilon=0.001)
        assert score == pytest.approx(0.0)


class TestMotionScoreMissingData:
    """Missing data handling."""

    def test_player_motion_none(self) -> None:
        ref = _make_motion([_lm()])
        score = compute_motion_score(None, ref)
        assert score is None

    def test_reference_motion_none(self) -> None:
        player = _make_motion([_lm()])
        score = compute_motion_score(player, None)
        assert score is None

    def test_landmark_motion_none_excluded(self) -> None:
        """None landmarks excluded, valid ones still scored."""
        p_lm = _lm(speed=2.0, dx=1.0, dy=0.0, dz=0.0)
        player = _make_motion([p_lm, None, p_lm])
        ref = _make_motion([p_lm, p_lm, p_lm])
        # 2 valid pairs (indices 0 and 2), identical → 100
        score = compute_motion_score(player, ref)
        assert score == pytest.approx(100.0)

    def test_no_valid_landmarks_returns_none(self) -> None:
        player = _make_motion([None, None])
        ref = _make_motion([None, None])
        score = compute_motion_score(player, ref)
        assert score is None


class TestMotionScoreConfig:
    """Configurable weights and epsilon."""

    def test_speed_weight_one_direction_zero(self) -> None:
        """All weight on speed: perpendicular direction doesn't matter."""
        p_lm = _lm(speed=2.0, dx=1.0, dy=0.0, dz=0.0)
        r_lm = _lm(speed=2.0, dx=0.0, dy=1.0, dz=0.0)
        player = _make_motion([p_lm])
        ref = _make_motion([r_lm])
        # speed_sim=1.0, direction ignored (weight=0)
        score = compute_motion_score(player, ref, speed_weight=1.0, direction_weight=0.0)
        assert score == pytest.approx(100.0)

    def test_direction_weight_one_speed_zero(self) -> None:
        """All weight on direction: speed mismatch doesn't matter."""
        p_lm = _lm(speed=1.0, dx=1.0, dy=0.0, dz=0.0)
        r_lm = _lm(speed=5.0, dx=1.0, dy=0.0, dz=0.0)
        player = _make_motion([p_lm])
        ref = _make_motion([r_lm])
        # dir_sim=1.0, speed ignored (weight=0)
        score = compute_motion_score(player, ref, speed_weight=0.0, direction_weight=1.0)
        assert score == pytest.approx(100.0)

    def test_custom_epsilon(self) -> None:
        """Large epsilon: both speeds below it → both still."""
        p_lm = _lm(speed=0.5, dx=1.0, dy=0.0, dz=0.0)
        r_lm = _lm(speed=0.3, dx=-1.0, dy=0.0, dz=0.0)
        player = _make_motion([p_lm])
        ref = _make_motion([r_lm])
        # epsilon=1.0 → both below → speed_sim=1, dir undefined → 100
        score = compute_motion_score(player, ref, epsilon=1.0)
        assert score == pytest.approx(100.0)


class TestMotionScoreBounded:
    """Score always in [0, 100]."""

    def test_never_negative(self) -> None:
        p_lm = _lm(speed=0.0, dx=0.0, dy=0.0, dz=0.0)
        r_lm = _lm(speed=10.0, dx=-1.0, dy=0.0, dz=0.0)
        player = _make_motion([p_lm])
        ref = _make_motion([r_lm])
        score = compute_motion_score(player, ref)
        assert score is not None
        assert score >= 0.0

    def test_never_above_100(self) -> None:
        lm = _lm(speed=2.0, dx=1.0, dy=0.0, dz=0.0)
        player = _make_motion([lm])
        ref = _make_motion([lm])
        score = compute_motion_score(player, ref)
        assert score is not None
        assert score <= 100.0


class TestMotionScoreDeterminism:
    """Deterministic repeated computation."""

    def test_same_input_same_output(self) -> None:
        p_lm = _lm(speed=1.5, dx=0.6, dy=0.8, dz=0.0)
        r_lm = _lm(speed=2.0, dx=0.8, dy=0.6, dz=0.0)
        player = _make_motion([p_lm, p_lm])
        ref = _make_motion([r_lm, r_lm])
        s1 = compute_motion_score(player, ref)
        s2 = compute_motion_score(player, ref)
        assert s1 == s2


class TestMotionScoreAccelerationExcluded:
    """Acceleration does NOT affect the motion score."""

    def test_different_acceleration_same_score(self) -> None:
        """Two landmarks with different acceleration but same speed/dir → same score."""
        lm1 = LandmarkMotion(
            velocity_x=1.0, velocity_y=0.0, velocity_z=0.0,
            speed=1.0, acceleration=0.0,
            direction_x=1.0, direction_y=0.0, direction_z=0.0,
        )
        lm2 = LandmarkMotion(
            velocity_x=1.0, velocity_y=0.0, velocity_z=0.0,
            speed=1.0, acceleration=999.0,  # wildly different acceleration
            direction_x=1.0, direction_y=0.0, direction_z=0.0,
        )
        player = _make_motion([lm1])
        ref = _make_motion([lm2])
        score = compute_motion_score(player, ref)
        assert score == pytest.approx(100.0)
