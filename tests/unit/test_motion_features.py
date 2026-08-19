"""Unit tests for motion feature extraction (central differences).

Tests compute_sequence_motion() with synthetic NormalizedPose sequences:
- Central difference for interior frames
- Forward difference at first frame
- Backward difference at last frame
- Zero dt → None
- None landmark propagation
- min_velocity_threshold zeroing
- Single frame → no velocity
- Two frames → forward/backward only
- Three frames → full central difference
- Acceleration via speed differences
"""

import math

import pytest

from opendance.config.models import MotionConfig
from opendance.motion.features import compute_sequence_motion
from opendance.motion.landmarks import NUM_LANDMARKS
from opendance.motion.normalized_pose import NormalizedPose


def _make_normalized_pose(
    timestamp_ms: int,
    x_offset: float = 0.0,
    y_offset: float = 0.0,
    z_offset: float = 0.0,
    include_none_landmark: int | None = None,
) -> NormalizedPose:
    """Create a NormalizedPose with all landmarks at (x_offset, y_offset, z_offset).

    If include_none_landmark is set, that landmark index will be None.
    """
    landmarks: list[tuple[float, float, float] | None] = []
    for i in range(NUM_LANDMARKS):
        if include_none_landmark is not None and i == include_none_landmark:
            landmarks.append(None)
        else:
            landmarks.append((x_offset, y_offset, z_offset))
    return NormalizedPose(
        timestamp_ms=timestamp_ms,
        landmarks_2d=tuple(landmarks),
        landmarks_3d=None,
        visibilities=tuple(1.0 for _ in range(NUM_LANDMARKS)),
        presences=tuple(1.0 for _ in range(NUM_LANDMARKS)),
        body_center=(0.0, 0.0, 0.0),
        body_scale=1.0,
        valid=True,
    )


class TestEmptyAndSingleFrame:
    """Edge cases: empty input and single frame."""

    def test_empty_sequence(self) -> None:
        result = compute_sequence_motion([])
        assert result == []

    def test_single_frame_no_velocity(self) -> None:
        pose = _make_normalized_pose(timestamp_ms=100)
        result = compute_sequence_motion([pose])
        assert len(result) == 1
        mf = result[0]
        assert mf is not None
        assert mf.timestamp_ms == 100
        # All motions should be None (can't compute velocity from 1 frame)
        assert all(lm is None for lm in mf.landmark_motions)

    def test_single_none_in_sequence(self) -> None:
        result = compute_sequence_motion([None])
        assert len(result) == 1
        assert result[0] is None


class TestTwoFrames:
    """Two frames: forward at first, backward at last."""

    def test_two_frames_uniform_motion(self) -> None:
        """Landmark moves 1.0 unit in x over 1 second."""
        p0 = _make_normalized_pose(timestamp_ms=0, x_offset=0.0)
        p1 = _make_normalized_pose(timestamp_ms=1000, x_offset=1.0)
        result = compute_sequence_motion([p0, p1])

        assert len(result) == 2

        # Frame 0: forward difference → velocity = (1.0 - 0.0) / 1.0 = 1.0 in x
        mf0 = result[0]
        assert mf0 is not None
        lm0 = mf0.landmark_motions[0]
        assert lm0 is not None
        assert lm0.velocity_x == pytest.approx(1.0)
        assert lm0.velocity_y == pytest.approx(0.0)
        assert lm0.velocity_z == pytest.approx(0.0)
        assert lm0.speed == pytest.approx(1.0)

        # Frame 1: backward difference → same velocity
        mf1 = result[1]
        assert mf1 is not None
        lm1 = mf1.landmark_motions[0]
        assert lm1 is not None
        assert lm1.velocity_x == pytest.approx(1.0)
        assert lm1.speed == pytest.approx(1.0)

    def test_two_frames_dt_seconds(self) -> None:
        p0 = _make_normalized_pose(timestamp_ms=0)
        p1 = _make_normalized_pose(timestamp_ms=500)
        result = compute_sequence_motion([p0, p1])

        mf0 = result[0]
        assert mf0 is not None
        assert mf0.dt_seconds == pytest.approx(0.5)


class TestThreeFramesCentralDifference:
    """Three frames: central difference for interior frame."""

    def test_central_difference_velocity(self) -> None:
        """Positions: 0, 1, 2 at times 0, 1000, 2000ms.
        Central diff at frame 1: v = (pos[2] - pos[0]) / (2*1.0) = (2-0)/2 = 1.0
        """
        p0 = _make_normalized_pose(timestamp_ms=0, x_offset=0.0)
        p1 = _make_normalized_pose(timestamp_ms=1000, x_offset=1.0)
        p2 = _make_normalized_pose(timestamp_ms=2000, x_offset=2.0)
        result = compute_sequence_motion([p0, p1, p2])

        assert len(result) == 3

        # Frame 1 (interior): central diff
        mf1 = result[1]
        assert mf1 is not None
        lm1 = mf1.landmark_motions[0]
        assert lm1 is not None
        # v = (2.0 - 0.0) / 2.0 = 1.0
        assert lm1.velocity_x == pytest.approx(1.0)
        assert lm1.speed == pytest.approx(1.0)
        assert mf1.dt_seconds == pytest.approx(2.0)  # span from frame 0 to 2

    def test_central_difference_with_acceleration(self) -> None:
        """Accelerating motion: positions 0, 1, 4 at equal time intervals.
        Speed at frame 0: forward diff = (1-0)/1 = 1.0
        Speed at frame 1: central diff = (4-0)/2 = 2.0
        Speed at frame 2: backward diff = (4-1)/1 = 3.0
        Acceleration at frame 1 (central on speed): (3.0 - 1.0) / 2.0 = 1.0
        """
        p0 = _make_normalized_pose(timestamp_ms=0, x_offset=0.0)
        p1 = _make_normalized_pose(timestamp_ms=1000, x_offset=1.0)
        p2 = _make_normalized_pose(timestamp_ms=2000, x_offset=4.0)
        result = compute_sequence_motion([p0, p1, p2])

        mf1 = result[1]
        assert mf1 is not None
        lm1 = mf1.landmark_motions[0]
        assert lm1 is not None
        assert lm1.acceleration == pytest.approx(1.0)


class TestZeroDt:
    """Zero time delta → None motion values."""

    def test_identical_timestamps_produce_none(self) -> None:
        p0 = _make_normalized_pose(timestamp_ms=100, x_offset=0.0)
        p1 = _make_normalized_pose(timestamp_ms=100, x_offset=1.0)
        result = compute_sequence_motion([p0, p1])

        # Both frames should have dt=0 → all None
        for mf in result:
            assert mf is not None
            assert all(lm is None for lm in mf.landmark_motions)


class TestNonePropagation:
    """None landmarks and None poses propagate correctly."""

    def test_none_pose_in_sequence(self) -> None:
        p0 = _make_normalized_pose(timestamp_ms=0, x_offset=0.0)
        p2 = _make_normalized_pose(timestamp_ms=2000, x_offset=2.0)
        result = compute_sequence_motion([p0, None, p2])

        assert len(result) == 3
        assert result[1] is None
        # Frame 0: forward difference requires frame 1 which is None → no velocity
        mf0 = result[0]
        assert mf0 is not None
        assert all(lm is None for lm in mf0.landmark_motions)

    def test_none_landmark_produces_none_motion(self) -> None:
        p0 = _make_normalized_pose(timestamp_ms=0, x_offset=0.0, include_none_landmark=5)
        p1 = _make_normalized_pose(timestamp_ms=1000, x_offset=1.0, include_none_landmark=5)
        result = compute_sequence_motion([p0, p1])

        # Landmark 5 is None → its motion should be None
        mf0 = result[0]
        assert mf0 is not None
        assert mf0.landmark_motions[5] is None
        # Other landmarks should have valid motion
        assert mf0.landmark_motions[0] is not None


class TestMinVelocityThreshold:
    """Speeds below min_velocity_threshold are zeroed."""

    def test_below_threshold_zeroed(self) -> None:
        """Tiny movement below threshold → speed=0."""
        config = MotionConfig(min_velocity_threshold=1.0)
        p0 = _make_normalized_pose(timestamp_ms=0, x_offset=0.0)
        p1 = _make_normalized_pose(timestamp_ms=1000, x_offset=0.001)  # speed=0.001 < 1.0
        result = compute_sequence_motion([p0, p1], config=config)

        mf0 = result[0]
        assert mf0 is not None
        lm0 = mf0.landmark_motions[0]
        assert lm0 is not None
        assert lm0.speed == 0.0
        assert lm0.velocity_x == 0.0

    def test_above_threshold_preserved(self) -> None:
        """Movement above threshold → actual values."""
        config = MotionConfig(min_velocity_threshold=0.01)
        p0 = _make_normalized_pose(timestamp_ms=0, x_offset=0.0)
        p1 = _make_normalized_pose(timestamp_ms=1000, x_offset=5.0)
        result = compute_sequence_motion([p0, p1], config=config)

        mf0 = result[0]
        assert mf0 is not None
        lm0 = mf0.landmark_motions[0]
        assert lm0 is not None
        assert lm0.speed == pytest.approx(5.0)


class TestDirectionVector:
    """Direction is a normalized displacement vector."""

    def test_direction_is_unit_vector(self) -> None:
        p0 = _make_normalized_pose(timestamp_ms=0, x_offset=0.0, y_offset=0.0)
        p1 = _make_normalized_pose(timestamp_ms=1000, x_offset=3.0, y_offset=4.0)
        result = compute_sequence_motion([p0, p1])

        mf0 = result[0]
        assert mf0 is not None
        lm0 = mf0.landmark_motions[0]
        assert lm0 is not None
        # Direction should be (3/5, 4/5, 0) = (0.6, 0.8, 0)
        assert lm0.direction_x == pytest.approx(0.6)
        assert lm0.direction_y == pytest.approx(0.8)
        assert lm0.direction_z == pytest.approx(0.0)
        # Verify unit length
        mag = math.sqrt(
            lm0.direction_x**2 + lm0.direction_y**2 + lm0.direction_z**2
        )
        assert mag == pytest.approx(1.0)


class TestInvalidPose:
    """Invalid poses (valid=False) produce None in output."""

    def test_invalid_pose_produces_none(self) -> None:
        p0 = _make_normalized_pose(timestamp_ms=0)
        invalid = NormalizedPose.invalid(timestamp_ms=1000)
        p2 = _make_normalized_pose(timestamp_ms=2000)
        result = compute_sequence_motion([p0, invalid, p2])

        assert result[1] is None
