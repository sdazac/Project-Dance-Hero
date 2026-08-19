"""Unit tests for pose normalization.

Tests normalize_pose() with synthetic PoseResult inputs covering:
- World-landmark preferred path
- Image-space fallback path
- min_body_scale invalidation
- Coordinate transformation correctness
- Visibility/presence preservation
- None propagation for unreliable landmarks
- timestamp_ms preservation
- Single-frame purity (no mutation)
- valid=False for insufficient data
"""

import math

import pytest

from opendance.config.models import NormalizationConfig
from opendance.motion.landmarks import (
    LEFT_HIP,
    LEFT_SHOULDER,
    NUM_LANDMARKS,
    RIGHT_HIP,
)
from opendance.motion.normalizer import normalize_pose
from opendance.pose.result import Landmark, PoseResult, WorldLandmark


def _make_landmark(
    x: float = 0.5, y: float = 0.5, z: float = 0.0,
    visibility: float = 1.0, presence: float = 1.0,
) -> Landmark:
    return Landmark(x=x, y=y, z=z, visibility=visibility, presence=presence)


def _make_world_landmark(
    x: float = 0.0, y: float = 0.0, z: float = 0.0,
    visibility: float = 1.0, presence: float = 1.0,
) -> WorldLandmark:
    return WorldLandmark(x=x, y=y, z=z, visibility=visibility, presence=presence)


def _make_full_pose_result(
    visibility: float = 1.0,
    timestamp_ms: int = 100,
    include_world: bool = True,
) -> PoseResult:
    """Create a PoseResult with all landmarks at known positions.

    Landmarks placed so:
    - left_hip (23) at (0.4, 0.6, 0.0)
    - right_hip (24) at (0.6, 0.6, 0.0)
    - left_shoulder (11) at (0.4, 0.3, 0.0)
    → body_center = (0.5, 0.6, 0.0)
    → body_scale = dist((0.4,0.3,0), (0.6,0.6,0)) = sqrt(0.04+0.09) = sqrt(0.13)
    """
    landmarks = []
    for i in range(NUM_LANDMARKS):
        if i == LEFT_HIP:
            landmarks.append(_make_landmark(0.4, 0.6, 0.0, visibility))
        elif i == RIGHT_HIP:
            landmarks.append(_make_landmark(0.6, 0.6, 0.0, visibility))
        elif i == LEFT_SHOULDER:
            landmarks.append(_make_landmark(0.4, 0.3, 0.0, visibility))
        else:
            landmarks.append(_make_landmark(0.5, 0.5, 0.0, visibility))

    world_landmarks: tuple[WorldLandmark, ...] = ()
    if include_world:
        wl = []
        for i in range(NUM_LANDMARKS):
            if i == LEFT_HIP:
                wl.append(_make_world_landmark(-0.1, -0.2, 0.0, visibility))
            elif i == RIGHT_HIP:
                wl.append(_make_world_landmark(0.1, -0.2, 0.0, visibility))
            elif i == LEFT_SHOULDER:
                wl.append(_make_world_landmark(-0.1, 0.3, 0.0, visibility))
            else:
                wl.append(_make_world_landmark(0.0, 0.0, 0.0, visibility))
        world_landmarks = tuple(wl)

    return PoseResult(
        landmarks=tuple(landmarks),
        world_landmarks=world_landmarks,
        timestamp_ms=timestamp_ms,
    )


DEFAULT_CONFIG = NormalizationConfig()


class TestNormalizationWorldPreferred:
    """World landmarks are used for center/scale when available and visible."""

    def test_uses_world_landmarks_for_center_and_scale(self) -> None:
        pose = _make_full_pose_result(include_world=True)
        result = normalize_pose(pose, DEFAULT_CONFIG)

        assert result.valid
        # World center = midpoint((-0.1,-0.2,0), (0.1,-0.2,0)) = (0, -0.2, 0)
        assert result.body_center == pytest.approx((0.0, -0.2, 0.0))
        # World scale = dist((-0.1,0.3,0), (0.1,-0.2,0)) = sqrt(0.04+0.25) = sqrt(0.29)
        expected_scale = math.sqrt(0.04 + 0.25)
        assert result.body_scale == pytest.approx(expected_scale)

    def test_landmarks_3d_populated_when_world_available(self) -> None:
        pose = _make_full_pose_result(include_world=True)
        result = normalize_pose(pose, DEFAULT_CONFIG)

        assert result.landmarks_3d is not None
        assert len(result.landmarks_3d) == NUM_LANDMARKS


class TestNormalizationImageFallback:
    """Falls back to image-space when world landmarks unavailable."""

    def test_uses_image_space_when_no_world(self) -> None:
        pose = _make_full_pose_result(include_world=False)
        result = normalize_pose(pose, DEFAULT_CONFIG)

        assert result.valid
        # Image center = midpoint((0.4,0.6,0), (0.6,0.6,0)) = (0.5, 0.6, 0)
        assert result.body_center == pytest.approx((0.5, 0.6, 0.0))
        # Image scale = dist((0.4,0.3,0), (0.6,0.6,0))
        expected_scale = math.sqrt(0.04 + 0.09)
        assert result.body_scale == pytest.approx(expected_scale)

    def test_landmarks_3d_is_none_when_no_world(self) -> None:
        pose = _make_full_pose_result(include_world=False)
        result = normalize_pose(pose, DEFAULT_CONFIG)

        assert result.landmarks_3d is None

    def test_falls_back_when_world_center_landmarks_unreliable(self) -> None:
        """If world hips have low visibility, fall back to image space."""
        landmarks = [_make_landmark(0.5, 0.5, 0.0, 1.0)] * NUM_LANDMARKS
        lm_list = list(landmarks)
        lm_list[LEFT_HIP] = _make_landmark(0.4, 0.6, 0.0, 1.0)
        lm_list[RIGHT_HIP] = _make_landmark(0.6, 0.6, 0.0, 1.0)
        lm_list[LEFT_SHOULDER] = _make_landmark(0.4, 0.3, 0.0, 1.0)

        # World landmarks with low visibility on hips
        wl = [_make_world_landmark(0.0, 0.0, 0.0, 1.0)] * NUM_LANDMARKS
        wl_list = list(wl)
        wl_list[LEFT_HIP] = _make_world_landmark(-0.1, -0.2, 0.0, 0.1)  # below threshold
        wl_list[RIGHT_HIP] = _make_world_landmark(0.1, -0.2, 0.0, 0.1)  # below threshold
        wl_list[LEFT_SHOULDER] = _make_world_landmark(-0.1, 0.3, 0.0, 1.0)

        pose = PoseResult(
            landmarks=tuple(lm_list),
            world_landmarks=tuple(wl_list),
            timestamp_ms=200,
        )
        result = normalize_pose(pose, DEFAULT_CONFIG)

        assert result.valid
        # Should use image-space center
        assert result.body_center == pytest.approx((0.5, 0.6, 0.0))


class TestMinBodyScale:
    """Body scale below min_body_scale produces invalid result."""

    def test_zero_scale_produces_invalid(self) -> None:
        """All landmarks at same position → scale = 0 → invalid."""
        landmarks = [_make_landmark(0.5, 0.5, 0.0, 1.0)] * NUM_LANDMARKS
        pose = PoseResult(landmarks=tuple(landmarks), world_landmarks=(), timestamp_ms=50)
        result = normalize_pose(pose, DEFAULT_CONFIG)

        assert not result.valid
        assert result.body_scale == 0.0

    def test_tiny_scale_below_epsilon(self) -> None:
        """Scale just below min_body_scale → invalid."""
        landmarks = [_make_landmark(0.5, 0.5, 0.0, 1.0)] * NUM_LANDMARKS
        lm_list = list(landmarks)
        lm_list[LEFT_HIP] = _make_landmark(0.5, 0.5, 0.0, 1.0)
        lm_list[RIGHT_HIP] = _make_landmark(0.5, 0.5, 0.0, 1.0)
        lm_list[LEFT_SHOULDER] = _make_landmark(0.5, 0.5 + 0.0001, 0.0, 1.0)

        pose = PoseResult(landmarks=tuple(lm_list), world_landmarks=(), timestamp_ms=50)
        config = NormalizationConfig(min_body_scale=0.001)
        result = normalize_pose(pose, config)

        assert not result.valid


class TestCoordinateTransformation:
    """Verify translate + scale produces correct body-normalized coords."""

    def test_body_center_normalizes_to_origin(self) -> None:
        pose = _make_full_pose_result(include_world=False)
        result = normalize_pose(pose, DEFAULT_CONFIG)

        # Center landmarks (hips midpoint) should normalize to ~(0,0,0)
        hip_l = result.landmarks_2d[LEFT_HIP]
        hip_r = result.landmarks_2d[RIGHT_HIP]
        assert hip_l is not None
        assert hip_r is not None
        mid_x = (hip_l[0] + hip_r[0]) / 2.0
        mid_y = (hip_l[1] + hip_r[1]) / 2.0
        assert mid_x == pytest.approx(0.0, abs=1e-9)
        assert mid_y == pytest.approx(0.0, abs=1e-9)

    def test_shoulder_hip_distance_equals_one(self) -> None:
        """After normalization, dist(left_shoulder, right_hip) should be 1.0."""
        pose = _make_full_pose_result(include_world=False)
        result = normalize_pose(pose, DEFAULT_CONFIG)

        shoulder = result.landmarks_2d[LEFT_SHOULDER]
        hip_r = result.landmarks_2d[RIGHT_HIP]
        assert shoulder is not None
        assert hip_r is not None
        dist = math.sqrt(
            (shoulder[0] - hip_r[0]) ** 2
            + (shoulder[1] - hip_r[1]) ** 2
            + (shoulder[2] - hip_r[2]) ** 2
        )
        assert dist == pytest.approx(1.0, abs=1e-9)


class TestVisibilityPresencePreservation:
    """Original visibility and presence values are preserved unchanged."""

    def test_visibilities_preserved(self) -> None:
        landmarks = []
        for i in range(NUM_LANDMARKS):
            vis = float(i) / NUM_LANDMARKS
            landmarks.append(_make_landmark(0.5, 0.5, 0.0, vis, 0.9))
        # Ensure body center/scale landmarks are visible
        landmarks[LEFT_HIP] = _make_landmark(0.4, 0.6, 0.0, 1.0, 0.9)
        landmarks[RIGHT_HIP] = _make_landmark(0.6, 0.6, 0.0, 1.0, 0.9)
        landmarks[LEFT_SHOULDER] = _make_landmark(0.4, 0.3, 0.0, 1.0, 0.9)

        pose = PoseResult(landmarks=tuple(landmarks), world_landmarks=(), timestamp_ms=0)
        result = normalize_pose(pose, DEFAULT_CONFIG)

        assert result.valid
        for i in range(NUM_LANDMARKS):
            if i in (LEFT_HIP, RIGHT_HIP, LEFT_SHOULDER):
                assert result.visibilities[i] == 1.0
            else:
                assert result.visibilities[i] == pytest.approx(float(i) / NUM_LANDMARKS)

    def test_presences_preserved(self) -> None:
        landmarks = [_make_landmark(0.5, 0.5, 0.0, 1.0, 0.77)] * NUM_LANDMARKS
        lm_list = list(landmarks)
        lm_list[LEFT_HIP] = _make_landmark(0.4, 0.6, 0.0, 1.0, 0.88)
        lm_list[RIGHT_HIP] = _make_landmark(0.6, 0.6, 0.0, 1.0, 0.88)
        lm_list[LEFT_SHOULDER] = _make_landmark(0.4, 0.3, 0.0, 1.0, 0.88)

        pose = PoseResult(landmarks=tuple(lm_list), world_landmarks=(), timestamp_ms=0)
        result = normalize_pose(pose, DEFAULT_CONFIG)

        assert result.presences[0] == 0.77
        assert result.presences[LEFT_HIP] == 0.88


class TestNonePropagation:
    """Low-visibility landmarks produce None in normalized output."""

    def test_low_visibility_produces_none(self) -> None:
        landmarks = [_make_landmark(0.5, 0.5, 0.0, 0.1, 1.0)] * NUM_LANDMARKS
        lm_list = list(landmarks)
        # Body center/scale landmarks must be visible
        lm_list[LEFT_HIP] = _make_landmark(0.4, 0.6, 0.0, 1.0, 1.0)
        lm_list[RIGHT_HIP] = _make_landmark(0.6, 0.6, 0.0, 1.0, 1.0)
        lm_list[LEFT_SHOULDER] = _make_landmark(0.4, 0.3, 0.0, 1.0, 1.0)

        pose = PoseResult(landmarks=tuple(lm_list), world_landmarks=(), timestamp_ms=0)
        result = normalize_pose(pose, DEFAULT_CONFIG)

        assert result.valid
        # Landmarks with visibility 0.1 < threshold 0.5 → None
        assert result.landmarks_2d[0] is None
        assert result.landmarks_2d[1] is None
        # Body landmarks are visible
        assert result.landmarks_2d[LEFT_HIP] is not None
        assert result.landmarks_2d[RIGHT_HIP] is not None
        assert result.landmarks_2d[LEFT_SHOULDER] is not None

    def test_both_hips_unreliable_produces_invalid(self) -> None:
        landmarks = [_make_landmark(0.5, 0.5, 0.0, 1.0)] * NUM_LANDMARKS
        lm_list = list(landmarks)
        lm_list[LEFT_HIP] = _make_landmark(0.4, 0.6, 0.0, 0.1)  # below threshold
        lm_list[RIGHT_HIP] = _make_landmark(0.6, 0.6, 0.0, 0.1)  # below threshold

        pose = PoseResult(landmarks=tuple(lm_list), world_landmarks=(), timestamp_ms=0)
        result = normalize_pose(pose, DEFAULT_CONFIG)

        assert not result.valid

    def test_one_hip_unreliable_uses_other(self) -> None:
        landmarks = [_make_landmark(0.5, 0.5, 0.0, 1.0)] * NUM_LANDMARKS
        lm_list = list(landmarks)
        lm_list[LEFT_HIP] = _make_landmark(0.4, 0.6, 0.0, 0.1)  # unreliable
        lm_list[RIGHT_HIP] = _make_landmark(0.6, 0.6, 0.0, 1.0)  # reliable
        lm_list[LEFT_SHOULDER] = _make_landmark(0.4, 0.3, 0.0, 1.0)

        pose = PoseResult(landmarks=tuple(lm_list), world_landmarks=(), timestamp_ms=0)
        result = normalize_pose(pose, DEFAULT_CONFIG)

        assert result.valid
        # Center should be the single reliable hip
        assert result.body_center == pytest.approx((0.6, 0.6, 0.0))


class TestTimestampPreservation:
    """timestamp_ms is copied unchanged from PoseResult."""

    def test_timestamp_preserved(self) -> None:
        pose = _make_full_pose_result(timestamp_ms=12345)
        result = normalize_pose(pose, DEFAULT_CONFIG)
        assert result.timestamp_ms == 12345


class TestPurityNoMutation:
    """normalize_pose does not modify input PoseResult."""

    def test_input_not_mutated(self) -> None:
        pose = _make_full_pose_result(timestamp_ms=500)
        original_landmarks = pose.landmarks
        original_world = pose.world_landmarks
        original_ts = pose.timestamp_ms

        normalize_pose(pose, DEFAULT_CONFIG)

        assert pose.landmarks is original_landmarks
        assert pose.world_landmarks is original_world
        assert pose.timestamp_ms == original_ts


class TestEmptyPoseResult:
    """Empty PoseResult produces invalid NormalizedPose."""

    def test_empty_pose_produces_invalid(self) -> None:
        pose = PoseResult.empty(timestamp_ms=999)
        result = normalize_pose(pose, DEFAULT_CONFIG)
        assert not result.valid
        assert result.timestamp_ms == 999
