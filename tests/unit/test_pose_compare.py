"""Unit tests for pose comparison (2D x,y Euclidean distance).

Tests compute_pose_score() with synthetic NormalizedPose data.
"""

import pytest

from opendance.motion.landmarks import NUM_LANDMARKS
from opendance.motion.normalized_pose import NormalizedPose
from opendance.scoring.pose_compare import compute_pose_score


def _make_pose(
    x: float = 0.0, y: float = 0.0, z: float = 0.0,
    none_indices: set[int] | None = None,
) -> NormalizedPose:
    """Create a NormalizedPose with all landmarks at (x, y, z)."""
    landmarks: list[tuple[float, float, float] | None] = []
    for i in range(NUM_LANDMARKS):
        if none_indices and i in none_indices:
            landmarks.append(None)
        else:
            landmarks.append((x, y, z))
    return NormalizedPose(
        timestamp_ms=0,
        landmarks_2d=tuple(landmarks),
        landmarks_3d=None,
        visibilities=tuple(1.0 for _ in range(NUM_LANDMARKS)),
        presences=tuple(1.0 for _ in range(NUM_LANDMARKS)),
        body_center=(0.0, 0.0, 0.0),
        body_scale=1.0,
        valid=True,
    )


class TestPoseScoreIdentical:
    """Identical poses → score 100."""

    def test_identical_poses(self) -> None:
        player = _make_pose(0.1, 0.2, 0.0)
        ref = _make_pose(0.1, 0.2, 0.0)
        score = compute_pose_score(player, ref)
        assert score == pytest.approx(100.0)


class TestPoseScoreKnownDisplacement:
    """Known displacement → expected score."""

    def test_mean_distance_0_25(self) -> None:
        """Mean 2D distance 0.25 with scale 200 → score = 100 - 50 = 50."""
        player = _make_pose(0.0, 0.0, 0.0)
        ref = _make_pose(0.25, 0.0, 0.0)  # x offset only
        score = compute_pose_score(player, ref, pose_scale_factor=200.0)
        assert score == pytest.approx(50.0)

    def test_mean_distance_0_5(self) -> None:
        """Mean 2D distance 0.5 with scale 200 → score = 0."""
        player = _make_pose(0.0, 0.0, 0.0)
        ref = _make_pose(0.5, 0.0, 0.0)
        score = compute_pose_score(player, ref, pose_scale_factor=200.0)
        assert score == pytest.approx(0.0)

    def test_large_distance_clamps_to_zero(self) -> None:
        """Mean distance > 0.5 → still 0 (not negative)."""
        player = _make_pose(0.0, 0.0, 0.0)
        ref = _make_pose(1.0, 0.0, 0.0)
        score = compute_pose_score(player, ref, pose_scale_factor=200.0)
        assert score == pytest.approx(0.0)


class TestPoseScoreZExcluded:
    """Z differences must NOT affect the pose score."""

    def test_z_difference_ignored(self) -> None:
        player = _make_pose(0.0, 0.0, 0.0)
        ref = _make_pose(0.0, 0.0, 5.0)  # Large z difference
        score = compute_pose_score(player, ref)
        # x,y are identical → distance = 0 → score = 100
        assert score == pytest.approx(100.0)


class TestPoseScoreMissingLandmarks:
    """Missing landmarks excluded, min_valid_landmarks threshold."""

    def test_some_none_excluded(self) -> None:
        """Landmarks where one side is None are excluded from mean."""
        player = _make_pose(0.0, 0.0, 0.0, none_indices={0, 1, 2})
        ref = _make_pose(0.0, 0.0, 0.0)
        # 30 valid pairs (33 - 3), all distance 0 → score 100
        score = compute_pose_score(player, ref, min_valid_landmarks=8)
        assert score == pytest.approx(100.0)

    def test_insufficient_valid_landmarks_returns_none(self) -> None:
        """Fewer than min_valid_landmarks → None."""
        many_none = set(range(30))  # Only 3 valid
        player = _make_pose(0.0, 0.0, 0.0, none_indices=many_none)
        ref = _make_pose(0.0, 0.0, 0.0)
        score = compute_pose_score(player, ref, min_valid_landmarks=8)
        assert score is None

    def test_all_none_returns_none(self) -> None:
        """All landmarks None → None."""
        all_none = set(range(NUM_LANDMARKS))
        player = _make_pose(0.0, 0.0, 0.0, none_indices=all_none)
        ref = _make_pose(0.0, 0.0, 0.0)
        score = compute_pose_score(player, ref, min_valid_landmarks=1)
        assert score is None


class TestPoseScoreScaleFactor:
    """Configured pose_scale_factor is respected."""

    def test_custom_scale_factor(self) -> None:
        """Scale 100: distance 0.5 → score = 100 - 50 = 50."""
        player = _make_pose(0.0, 0.0, 0.0)
        ref = _make_pose(0.5, 0.0, 0.0)
        score = compute_pose_score(player, ref, pose_scale_factor=100.0)
        assert score == pytest.approx(50.0)


class TestPoseScoreBounded:
    """Score always in [0, 100]."""

    def test_never_negative(self) -> None:
        player = _make_pose(0.0, 0.0, 0.0)
        ref = _make_pose(10.0, 10.0, 0.0)
        score = compute_pose_score(player, ref)
        assert score is not None
        assert score >= 0.0

    def test_never_above_100(self) -> None:
        player = _make_pose(0.5, 0.5, 0.0)
        ref = _make_pose(0.5, 0.5, 0.0)
        score = compute_pose_score(player, ref)
        assert score is not None
        assert score <= 100.0
