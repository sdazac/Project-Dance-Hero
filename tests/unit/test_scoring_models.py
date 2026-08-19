"""Unit tests for Phase 3 scoring data models and LANDMARK_REGIONS.

Tests:
- EventRating enum members
- FeedbackItem construction and immutability
- FrameComparison construction
- LANDMARK_REGIONS completeness (all 33 indices)
- LANDMARK_REGIONS valid region names
- LANDMARK_REGIONS deterministic mapping
- Specific landmark-to-region assignments
"""

from opendance.scoring.models import (
    LANDMARK_REGIONS,
    EventRating,
    FeedbackItem,
    FrameComparison,
)


class TestEventRating:
    """Test EventRating enum."""

    def test_all_members_exist(self) -> None:
        assert EventRating.PERFECT.value == "PERFECT"
        assert EventRating.GREAT.value == "GREAT"
        assert EventRating.OK.value == "OK"
        assert EventRating.MEH.value == "MEH"
        assert EventRating.MISS.value == "MISS"

    def test_exactly_five_members(self) -> None:
        assert len(EventRating) == 5


class TestFeedbackItem:
    """Test FeedbackItem dataclass."""

    def test_construction(self) -> None:
        item = FeedbackItem(
            body_region="left_arm",
            issue_type="angle_mismatch",
            severity=0.75,
            description="left elbow angle differs by 67°",
        )
        assert item.body_region == "left_arm"
        assert item.issue_type == "angle_mismatch"
        assert item.severity == 0.75
        assert "67°" in item.description

    def test_immutability(self) -> None:
        item = FeedbackItem("torso", "position_off", 0.5, "test")
        try:
            item.severity = 0.9  # type: ignore[misc]
            assert False, "Should not allow mutation"
        except AttributeError:
            pass


class TestFrameComparison:
    """Test FrameComparison dataclass."""

    def test_construction_all_scores(self) -> None:
        fc = FrameComparison(
            timestamp_ms=1000,
            pose_score=85.0,
            angle_score=90.0,
            motion_score=75.0,
            timing_score=80.0,
            combined_score=83.5,
            event_rating=EventRating.GREAT,
            feedback=(),
        )
        assert fc.timestamp_ms == 1000
        assert fc.pose_score == 85.0
        assert fc.combined_score == 83.5
        assert fc.event_rating == EventRating.GREAT

    def test_construction_with_none_scores(self) -> None:
        fc = FrameComparison(
            timestamp_ms=500,
            pose_score=None,
            angle_score=None,
            motion_score=None,
            timing_score=None,
            combined_score=None,
            event_rating=EventRating.MISS,
            feedback=(),
        )
        assert fc.pose_score is None
        assert fc.combined_score is None
        assert fc.event_rating == EventRating.MISS

    def test_feedback_tuple(self) -> None:
        item = FeedbackItem("right_leg", "timing_phase_mismatch", 0.3, "late")
        fc = FrameComparison(
            timestamp_ms=0,
            pose_score=50.0,
            angle_score=None,
            motion_score=None,
            timing_score=None,
            combined_score=50.0,
            event_rating=EventRating.OK,
            feedback=(item,),
        )
        assert len(fc.feedback) == 1
        assert fc.feedback[0].body_region == "right_leg"


class TestLandmarkRegions:
    """Test LANDMARK_REGIONS mapping."""

    def test_covers_all_33_landmarks(self) -> None:
        """Every index 0-32 must be in the mapping."""
        for i in range(33):
            assert i in LANDMARK_REGIONS, f"Landmark {i} missing from LANDMARK_REGIONS"

    def test_no_extra_indices(self) -> None:
        """No indices outside 0-32."""
        for idx in LANDMARK_REGIONS:
            assert 0 <= idx <= 32

    def test_valid_region_names(self) -> None:
        """All values are one of the 6 valid regions."""
        valid_regions = {"face", "left_arm", "right_arm", "torso", "left_leg", "right_leg"}
        for idx, region in LANDMARK_REGIONS.items():
            assert region in valid_regions, f"Landmark {idx} has invalid region '{region}'"

    def test_face_landmarks(self) -> None:
        """Landmarks 0-10 are face."""
        for i in range(11):
            assert LANDMARK_REGIONS[i] == "face"

    def test_left_arm_landmarks(self) -> None:
        """Landmarks 11, 13, 15, 17, 19, 21 are left_arm."""
        for i in [11, 13, 15, 17, 19, 21]:
            assert LANDMARK_REGIONS[i] == "left_arm"

    def test_right_arm_landmarks(self) -> None:
        """Landmarks 12, 14, 16, 18, 20, 22 are right_arm."""
        for i in [12, 14, 16, 18, 20, 22]:
            assert LANDMARK_REGIONS[i] == "right_arm"

    def test_torso_landmarks(self) -> None:
        """Landmarks 23, 24 are torso."""
        assert LANDMARK_REGIONS[23] == "torso"
        assert LANDMARK_REGIONS[24] == "torso"

    def test_left_leg_landmarks(self) -> None:
        """Landmarks 25, 27, 29, 31 are left_leg."""
        for i in [25, 27, 29, 31]:
            assert LANDMARK_REGIONS[i] == "left_leg"

    def test_right_leg_landmarks(self) -> None:
        """Landmarks 26, 28, 30, 32 are right_leg."""
        for i in [26, 28, 30, 32]:
            assert LANDMARK_REGIONS[i] == "right_leg"

    def test_deterministic(self) -> None:
        """Same mapping on repeated access."""
        for i in range(33):
            assert LANDMARK_REGIONS[i] == LANDMARK_REGIONS[i]
