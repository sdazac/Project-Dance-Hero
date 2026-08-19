"""Unit tests for feedback generation.

Tests generate_feedback() for angle and position feedback with severity,
thresholds, LANDMARK_REGIONS, deterministic ordering, and missing data.
"""

import pytest

from opendance.motion.landmarks import NUM_LANDMARKS
from opendance.motion.normalized_pose import NormalizedPose
from opendance.scoring.feedback import generate_feedback


def _make_pose(
    x: float = 0.0, y: float = 0.0,
    none_indices: set[int] | None = None,
) -> NormalizedPose:
    landmarks: list[tuple[float, float, float] | None] = []
    for i in range(NUM_LANDMARKS):
        if none_indices and i in none_indices:
            landmarks.append(None)
        else:
            landmarks.append((x, y, 0.0))
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


class TestFeedbackNoErrors:
    """No errors → empty feedback."""

    def test_identical_poses_and_angles(self) -> None:
        pose = _make_pose(0.5, 0.5)
        angles = {"left_elbow": 90.0, "right_elbow": -45.0}
        items = generate_feedback(pose, pose, angles, angles)
        assert items == []


class TestAngleFeedback:
    """Angle mismatch feedback."""

    def test_significant_angle_error(self) -> None:
        """45° error > 0.1*180=18° threshold → feedback emitted.
        severity = 45/90 = 0.5.
        """
        pose = _make_pose()
        p_angles = {"left_elbow": 90.0}
        r_angles = {"left_elbow": 45.0}
        items = generate_feedback(pose, pose, p_angles, r_angles, 0.1)
        assert len(items) == 1
        assert items[0].body_region == "left_elbow"
        assert items[0].issue_type == "angle_mismatch"
        assert items[0].severity == pytest.approx(0.5)
        assert "45" in items[0].description

    def test_insignificant_angle_error(self) -> None:
        """5° error < 0.1*180=18° threshold → no feedback."""
        pose = _make_pose()
        p_angles = {"left_elbow": 90.0}
        r_angles = {"left_elbow": 85.0}
        items = generate_feedback(pose, pose, p_angles, r_angles, 0.1)
        assert len(items) == 0

    def test_angle_at_threshold_no_feedback(self) -> None:
        """18° error == 0.1*180=18° threshold → NOT > → no feedback."""
        pose = _make_pose()
        p_angles = {"left_elbow": 90.0}
        r_angles = {"left_elbow": 72.0}
        items = generate_feedback(pose, pose, p_angles, r_angles, 0.1)
        # error = 18°, threshold = 18° → not strictly greater → no feedback
        assert len(items) == 0

    def test_angle_just_above_threshold(self) -> None:
        """19° error > 0.1*180=18° threshold → feedback emitted."""
        pose = _make_pose()
        p_angles = {"left_elbow": 90.0}
        r_angles = {"left_elbow": 71.0}
        items = generate_feedback(pose, pose, p_angles, r_angles, 0.1)
        assert len(items) == 1
        assert items[0].issue_type == "angle_mismatch"

    def test_angle_wraparound(self) -> None:
        """-179° vs +179° → error = 2° < 18° → no feedback."""
        pose = _make_pose()
        p_angles = {"left_elbow": -179.0}
        r_angles = {"left_elbow": 179.0}
        items = generate_feedback(pose, pose, p_angles, r_angles, 0.1)
        assert len(items) == 0

    def test_angle_severity_capped_at_one(self) -> None:
        """180° error → severity = min(1.0, 180/90) = 1.0."""
        pose = _make_pose()
        p_angles = {"left_elbow": 0.0}
        r_angles = {"left_elbow": 180.0}
        items = generate_feedback(pose, pose, p_angles, r_angles, 0.0)
        assert len(items) == 1
        assert items[0].severity == pytest.approx(1.0)

    def test_custom_significance_threshold(self) -> None:
        """threshold=0.5 → angle emission requires error > 0.5*180=90°."""
        pose = _make_pose()
        p_angles = {"left_elbow": 0.0}
        r_angles = {"left_elbow": 80.0}  # 80° error < 90° threshold
        items = generate_feedback(pose, pose, p_angles, r_angles, 0.5)
        angle_items = [i for i in items if i.issue_type == "angle_mismatch"]
        assert len(angle_items) == 0

        r_angles2 = {"left_elbow": -95.0}  # 95° error > 90° threshold
        items2 = generate_feedback(pose, pose, p_angles, r_angles2, 0.5)
        angle_items2 = [i for i in items2 if i.issue_type == "angle_mismatch"]
        assert len(angle_items2) == 1

    def test_missing_player_angle_no_feedback(self) -> None:
        pose = _make_pose()
        p_angles = {"left_elbow": None}
        r_angles = {"left_elbow": 90.0}
        items = generate_feedback(pose, pose, p_angles, r_angles, 0.0)
        angle_items = [i for i in items if i.issue_type == "angle_mismatch"]
        assert len(angle_items) == 0

    def test_missing_reference_angle_no_feedback(self) -> None:
        pose = _make_pose()
        p_angles = {"left_elbow": 90.0}
        r_angles = {"left_elbow": None}
        items = generate_feedback(pose, pose, p_angles, r_angles, 0.0)
        angle_items = [i for i in items if i.issue_type == "angle_mismatch"]
        assert len(angle_items) == 0


class TestPositionFeedback:
    """Position mismatch feedback."""

    def test_significant_position_error(self) -> None:
        """Distance 0.3 → severity = 0.3/0.5 = 0.6 > threshold 0.1."""
        player = _make_pose(0.0, 0.0)
        ref = _make_pose(0.3, 0.0)
        items = generate_feedback(player, ref, {}, {}, 0.1)
        assert len(items) > 0
        assert all(i.issue_type == "position_off" for i in items)
        assert items[0].severity == pytest.approx(0.6)

    def test_insignificant_position_error(self) -> None:
        """Distance 0.05 → severity = 0.05/0.5 = 0.1 → not > threshold 0.1."""
        player = _make_pose(0.0, 0.0)
        ref = _make_pose(0.05, 0.0)
        items = generate_feedback(player, ref, {}, {}, 0.1)
        # distance=0.05 which is not > 0.1 threshold → no feedback
        assert len(items) == 0

    def test_position_severity_capped(self) -> None:
        """Distance 1.0 → severity = min(1.0, 1.0/0.5) = 1.0."""
        player = _make_pose(0.0, 0.0)
        ref = _make_pose(1.0, 0.0)
        items = generate_feedback(player, ref, {}, {}, 0.0)
        assert len(items) > 0
        assert items[0].severity == pytest.approx(1.0)

    def test_missing_landmark_no_feedback(self) -> None:
        """None landmarks produce no feedback."""
        player = _make_pose(0.0, 0.0, none_indices={0, 1, 2})
        ref = _make_pose(1.0, 1.0)
        items = generate_feedback(player, ref, {}, {}, 0.0)
        # Landmarks 0,1,2 are None on player side → should not appear
        for item in items:
            assert "(landmark 0)" not in item.description
            assert "(landmark 1)" not in item.description
            assert "(landmark 2)" not in item.description


class TestFeedbackLandmarkRegions:
    """LANDMARK_REGIONS used correctly."""

    def test_body_region_from_mapping(self) -> None:
        """Landmark 13 (left elbow) → region 'left_arm'."""
        player_lm = [None] * NUM_LANDMARKS
        ref_lm = [None] * NUM_LANDMARKS
        player_lm[13] = (0.0, 0.0, 0.0)
        ref_lm[13] = (0.5, 0.0, 0.0)  # distance 0.5

        player = NormalizedPose(
            timestamp_ms=0, landmarks_2d=tuple(player_lm), landmarks_3d=None,
            visibilities=tuple(1.0 for _ in range(NUM_LANDMARKS)),
            presences=tuple(1.0 for _ in range(NUM_LANDMARKS)),
            body_center=(0.0, 0.0, 0.0), body_scale=1.0, valid=True,
        )
        ref = NormalizedPose(
            timestamp_ms=0, landmarks_2d=tuple(ref_lm), landmarks_3d=None,
            visibilities=tuple(1.0 for _ in range(NUM_LANDMARKS)),
            presences=tuple(1.0 for _ in range(NUM_LANDMARKS)),
            body_center=(0.0, 0.0, 0.0), body_scale=1.0, valid=True,
        )
        items = generate_feedback(player, ref, {}, {}, 0.0)
        assert len(items) == 1
        assert items[0].body_region == "left_arm"


class TestFeedbackOrdering:
    """Deterministic ordering."""

    def test_angles_before_positions(self) -> None:
        """Angle feedback comes before position feedback."""
        player = _make_pose(0.0, 0.0)
        ref = _make_pose(0.3, 0.0)
        p_angles = {"left_elbow": 0.0}
        r_angles = {"left_elbow": 90.0}  # 90° error
        items = generate_feedback(player, ref, p_angles, r_angles, 0.0)

        angle_items = [i for i in items if i.issue_type == "angle_mismatch"]
        pos_items = [i for i in items if i.issue_type == "position_off"]
        assert len(angle_items) > 0
        assert len(pos_items) > 0
        # First items should be angle feedback
        assert items[0].issue_type == "angle_mismatch"

    def test_deterministic_repeated(self) -> None:
        player = _make_pose(0.0, 0.0)
        ref = _make_pose(0.2, 0.2)
        angles_p = {"left_elbow": 0.0, "right_knee": 90.0}
        angles_r = {"left_elbow": 45.0, "right_knee": 120.0}
        items1 = generate_feedback(player, ref, angles_p, angles_r, 0.0)
        items2 = generate_feedback(player, ref, angles_p, angles_r, 0.0)
        assert items1 == items2


class TestFeedbackThresholdConfig:
    """Configured significance threshold."""

    def test_high_threshold_filters_more(self) -> None:
        player = _make_pose(0.0, 0.0)
        ref = _make_pose(0.2, 0.0)
        # distance=0.2, severity=0.4
        items_low = generate_feedback(player, ref, {}, {}, 0.1)
        items_high = generate_feedback(player, ref, {}, {}, 0.5)
        # threshold 0.1: distance 0.2 > 0.1 → feedback
        assert len(items_low) > 0
        # threshold 0.5: distance 0.2 not > 0.5 → no feedback
        assert len(items_high) == 0


class TestFeedbackDescriptions:
    """Descriptions are measurable."""

    def test_angle_description_contains_degrees(self) -> None:
        pose = _make_pose()
        items = generate_feedback(
            pose, pose,
            {"left_elbow": 0.0}, {"left_elbow": 60.0},
            0.0,
        )
        assert len(items) >= 1
        assert "60" in items[0].description
        assert "\u00b0" in items[0].description  # degree symbol

    def test_position_description_contains_distance(self) -> None:
        player = _make_pose(0.0, 0.0)
        ref = _make_pose(0.25, 0.0)
        items = generate_feedback(player, ref, {}, {}, 0.0)
        assert len(items) > 0
        assert "0.250" in items[0].description
        assert "body-units" in items[0].description
