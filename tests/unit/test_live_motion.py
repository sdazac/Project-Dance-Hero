"""Unit tests for the pure current-frame motion helper.

Tests ``motion_for_latest(pose_buffer, config)`` from
``opendance.motion.live_motion``. The helper reuses ``compute_sequence_motion``
over a short oldest -> newest buffer and returns motion features for the LAST
(current) frame. These tests are pure: no Qt, camera, or MediaPipe.

Covered cases:
- Fewer than two poses (empty, single) -> None.
- Two poses with a known displacement over a known dt -> expected latest-frame
  speed/velocity for the moved landmark (displacement above the configured
  min_velocity_threshold so it is not zeroed).
- Equal timestamps (dt=0) -> no error; result is an is_empty MotionFeatures
  (the observed behavior of compute_sequence_motion for a 2-frame equal-timestamp
  list) rather than a raised exception.
- N-pose buffer -> motion features for the last pose (timestamp matches).
"""

import pytest

from opendance.config.models import MotionConfig
from opendance.motion.landmarks import LEFT_WRIST, NUM_LANDMARKS
from opendance.motion.live_motion import motion_for_latest
from opendance.motion.motion_result import MotionFeatures
from opendance.motion.normalized_pose import NormalizedPose


def _make_normalized_pose(
    timestamp_ms: int,
    moved_landmark: int | None = None,
    moved_position: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> NormalizedPose:
    """Build a valid NormalizedPose with all NUM_LANDMARKS landmarks present.

    All landmarks default to (0, 0, 0). If ``moved_landmark`` is given, that
    single landmark is placed at ``moved_position`` so a known displacement can
    be measured between frames.
    """
    landmarks: list[tuple[float, float, float] | None] = []
    for i in range(NUM_LANDMARKS):
        if moved_landmark is not None and i == moved_landmark:
            landmarks.append(moved_position)
        else:
            landmarks.append((0.0, 0.0, 0.0))
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


class TestInsufficientPoses:
    """Fewer than two poses cannot yield velocity -> None."""

    def test_empty_buffer_returns_none(self) -> None:
        assert motion_for_latest([], MotionConfig()) is None

    def test_single_pose_returns_none(self) -> None:
        pose = _make_normalized_pose(timestamp_ms=0)
        assert motion_for_latest([pose], MotionConfig()) is None


class TestTwoPosesKnownDisplacement:
    """Two poses with a known displacement over a known dt."""

    def test_latest_frame_speed_and_velocity(self) -> None:
        """Landmark moves (0.2, 0.0, 0.0) over 100ms.

        dt = 0.1s, so velocity_x = 0.2 / 0.1 = 2.0, speed = 2.0. The displacement
        magnitude (0.2) is well above the default min_velocity_threshold (0.01),
        so it is not zeroed. The returned features are for the LAST pose, whose
        timestamp is 100ms.
        """
        config = MotionConfig()
        # Guard against future default changes: displacement must exceed threshold.
        assert 0.2 > config.min_velocity_threshold

        p0 = _make_normalized_pose(
            timestamp_ms=0, moved_landmark=LEFT_WRIST, moved_position=(0.0, 0.0, 0.0)
        )
        p1 = _make_normalized_pose(
            timestamp_ms=100, moved_landmark=LEFT_WRIST, moved_position=(0.2, 0.0, 0.0)
        )

        result = motion_for_latest([p0, p1], config)

        assert result is not None
        # Backward difference at the last frame -> features are for the latest pose.
        assert result.timestamp_ms == 100
        assert result.dt_seconds == pytest.approx(0.1)

        lm = result.landmark_motions[LEFT_WRIST]
        assert lm is not None
        # velocity_x = displacement / dt = 0.2 / 0.1 = 2.0
        assert lm.velocity_x == pytest.approx(2.0)
        assert lm.velocity_y == pytest.approx(0.0)
        assert lm.velocity_z == pytest.approx(0.0)
        assert lm.speed == pytest.approx(2.0)


class TestEqualTimestamps:
    """Equal timestamps -> dt=0 handled without error."""

    def test_equal_timestamps_no_error_and_empty_motion(self) -> None:
        """Two poses with the SAME timestamp yield dt=0.

        Observed behavior of compute_sequence_motion for a 2-frame equal-timestamp
        list: it returns a MotionFeatures whose landmark_motions are all None
        (is_empty True) rather than raising or returning None. motion_for_latest
        returns that last element. We accept either None or an is_empty
        MotionFeatures and assert no exception is raised.
        """
        p0 = _make_normalized_pose(
            timestamp_ms=50, moved_landmark=LEFT_WRIST, moved_position=(0.0, 0.0, 0.0)
        )
        p1 = _make_normalized_pose(
            timestamp_ms=50, moved_landmark=LEFT_WRIST, moved_position=(0.2, 0.0, 0.0)
        )

        result = motion_for_latest([p0, p1], MotionConfig())

        if result is not None:
            assert isinstance(result, MotionFeatures)
            assert result.is_empty
            assert result.timestamp_ms == 50


class TestNPoseBuffer:
    """A longer buffer yields motion for the last pose."""

    def test_motion_for_last_pose(self) -> None:
        """Four poses with increasing timestamps; result matches the last pose."""
        poses = [
            _make_normalized_pose(
                timestamp_ms=ts,
                moved_landmark=LEFT_WRIST,
                moved_position=(x, 0.0, 0.0),
            )
            for ts, x in [(0, 0.0), (100, 0.2), (200, 0.4), (300, 0.6)]
        ]

        result = motion_for_latest(poses, MotionConfig())

        assert result is not None
        assert result.timestamp_ms == 300
