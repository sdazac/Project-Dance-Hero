"""Unit tests for skeleton renderer visibility threshold behavior.

Property 7: Skeleton rendering respects visibility threshold.
- Landmark drawn iff visibility >= threshold.
- Connection drawn iff BOTH endpoints meet threshold.
- Empty PoseResult → frame byte-identical.
- Boundary values: threshold 0.0, 1.0, visibility exactly equal to threshold.
"""

import numpy as np

from opendance.pose.result import Landmark, PoseResult
from opendance.ui.skeleton_renderer import render_skeleton


def _make_landmark(
    x: float = 0.5, y: float = 0.5, z: float = 0.0,
    visibility: float = 1.0, presence: float = 1.0
) -> Landmark:
    return Landmark(x=x, y=y, z=z, visibility=visibility, presence=presence)


def _make_pose_result(visibility: float, n_landmarks: int = 33) -> PoseResult:
    """Create a PoseResult with n_landmarks all at center with given visibility."""
    landmarks = tuple(
        _make_landmark(
            x=(i % 10) / 10.0 + 0.1,
            y=(i // 10) / 10.0 + 0.1,
            visibility=visibility,
        )
        for i in range(n_landmarks)
    )
    return PoseResult(landmarks=landmarks, world_landmarks=(), timestamp_ms=0)


class TestEmptyPoseResult:
    """Empty PoseResult leaves frame byte-identical."""

    def test_empty_result_frame_unchanged(self) -> None:
        frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
        original = frame.copy()
        result = render_skeleton(frame, PoseResult.empty())
        assert np.array_equal(result, original)

    def test_empty_result_returns_same_object(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = render_skeleton(frame, PoseResult.empty())
        assert result is frame


class TestVisibilityThreshold:
    """Landmark drawn iff visibility >= threshold."""

    def test_landmark_drawn_when_visibility_above_threshold(self) -> None:
        """Visibility 0.8 >= threshold 0.5 → frame modified."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        original = frame.copy()
        pose = _make_pose_result(visibility=0.8)
        render_skeleton(frame, pose, visibility_threshold=0.5)
        assert not np.array_equal(frame, original)

    def test_landmark_not_drawn_when_visibility_below_threshold(self) -> None:
        """Visibility 0.3 < threshold 0.5 → frame unchanged."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        original = frame.copy()
        pose = _make_pose_result(visibility=0.3)
        render_skeleton(frame, pose, visibility_threshold=0.5)
        assert np.array_equal(frame, original)

    def test_landmark_drawn_when_visibility_equals_threshold(self) -> None:
        """Visibility == threshold → landmark drawn (>= semantics)."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        original = frame.copy()
        pose = _make_pose_result(visibility=0.5)
        render_skeleton(frame, pose, visibility_threshold=0.5)
        assert not np.array_equal(frame, original)

    def test_threshold_zero_draws_all(self) -> None:
        """Threshold 0.0 → all landmarks drawn (visibility is always >= 0.0)."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        original = frame.copy()
        pose = _make_pose_result(visibility=0.0)
        render_skeleton(frame, pose, visibility_threshold=0.0)
        assert not np.array_equal(frame, original)

    def test_threshold_one_requires_full_visibility(self) -> None:
        """Threshold 1.0 → only landmarks with visibility=1.0 drawn."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        original = frame.copy()
        # visibility=0.99 < threshold=1.0 → not drawn
        pose = _make_pose_result(visibility=0.99)
        render_skeleton(frame, pose, visibility_threshold=1.0)
        assert np.array_equal(frame, original)

    def test_threshold_one_draws_when_visibility_is_one(self) -> None:
        """Visibility exactly 1.0 with threshold 1.0 → drawn."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        original = frame.copy()
        pose = _make_pose_result(visibility=1.0)
        render_skeleton(frame, pose, visibility_threshold=1.0)
        assert not np.array_equal(frame, original)


class TestConnectionVisibility:
    """Connections drawn only when BOTH endpoints meet threshold."""

    def test_connection_drawn_when_both_above(self) -> None:
        """Both landmarks visible → connection drawn."""
        # Use landmarks 11 and 12 (shoulders connection)
        landmarks = [_make_landmark(x=0.3, y=0.3, visibility=0.1)] * 33
        # Set landmarks 11 and 12 to high visibility at distinct positions
        lm_list = list(landmarks)
        lm_list[11] = _make_landmark(x=0.3, y=0.5, visibility=0.9)
        lm_list[12] = _make_landmark(x=0.7, y=0.5, visibility=0.9)
        pose = PoseResult(landmarks=tuple(lm_list), world_landmarks=(), timestamp_ms=0)

        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        original = frame.copy()
        render_skeleton(frame, pose, visibility_threshold=0.8)
        # Frame should be modified (connection between 11 and 12)
        assert not np.array_equal(frame, original)

    def test_connection_not_drawn_when_one_below(self) -> None:
        """One landmark below threshold → connection NOT drawn."""
        landmarks = [_make_landmark(x=0.5, y=0.5, visibility=0.1)] * 33
        lm_list = list(landmarks)
        lm_list[11] = _make_landmark(x=0.3, y=0.5, visibility=0.9)  # above
        lm_list[12] = _make_landmark(x=0.7, y=0.5, visibility=0.3)  # below
        pose = PoseResult(landmarks=tuple(lm_list), world_landmarks=(), timestamp_ms=0)

        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        render_skeleton(frame, pose, visibility_threshold=0.8)
        # Only landmark 11 should be drawn as a point, no connection
        # But even the single point makes frame != original
        # Check specifically that the line between them is NOT drawn
        # by checking that pixels along the path are still black
        # The line from (0.3*200, 0.5*200)=(60,100) to (0.7*200, 0.5*200)=(140,100)
        midpoint_pixel = frame[100, 100]  # midpoint of the connection
        assert np.array_equal(midpoint_pixel, [0, 0, 0])

    def test_connection_not_drawn_when_both_below(self) -> None:
        """Both landmarks below threshold → nothing drawn."""
        landmarks = [_make_landmark(x=0.5, y=0.5, visibility=0.1)] * 33
        pose = PoseResult(landmarks=tuple(landmarks), world_landmarks=(), timestamp_ms=0)

        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        original = frame.copy()
        render_skeleton(frame, pose, visibility_threshold=0.5)
        assert np.array_equal(frame, original)


class TestMixedVisibility:
    """Test mixed visibility across landmarks."""

    def test_only_visible_landmarks_drawn(self) -> None:
        """Mix of high and low visibility — only high ones produce marks."""
        landmarks_list = []
        for i in range(33):
            # Even indices: high visibility; odd: low
            vis = 0.9 if i % 2 == 0 else 0.1
            landmarks_list.append(
                _make_landmark(x=(i % 10) / 10.0 + 0.05, y=i / 33.0, visibility=vis)
            )
        pose = PoseResult(
            landmarks=tuple(landmarks_list), world_landmarks=(), timestamp_ms=0
        )

        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        original = frame.copy()
        render_skeleton(frame, pose, visibility_threshold=0.5)
        # Frame should be modified (some landmarks drawn)
        assert not np.array_equal(frame, original)
