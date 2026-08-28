"""Unit tests for SessionTracker combo semantics and grade boundaries.

Tests ``opendance.scoring.session_tracker.SessionTracker``, which tracks combo,
multiplier, and continuous accuracy, and maps accuracy to a categorical grade.
These tests are pure: no Qt event loop, no camera, no MediaPipe.

Covers:
- Combo semantics (task 4.3): only PERFECT/GREAT increment combo and bump the
  multiplier; OK/MEH/MISS reset combo to 0 and multiplier to 1.0.
- Multiplier increments (+0.10 PERFECT, +0.05 GREAT) and the 4.0 cap.
- Grade band boundaries (task 4.4) verified by calling ``_calculate_grade``
  directly at exact accuracy values.
- The continuous-accuracy property: ``accuracy_percentage`` is a float in
  [0, 100] and is not collapsed to a grade category.
"""

import pytest

from opendance.scoring.models import EventRating
from opendance.scoring.session_tracker import SessionTracker


class TestComboSemantics:
    """Combo and multiplier behavior per product.md rules (Requirements 5.1-5.5)."""

    def test_perfect_increments_combo(self) -> None:
        tracker = SessionTracker()
        tracker.update_with_rating(EventRating.PERFECT)
        tracker.update_with_rating(EventRating.PERFECT)
        assert tracker.state.combo == 2

    def test_great_increments_combo(self) -> None:
        tracker = SessionTracker()
        tracker.update_with_rating(EventRating.GREAT)
        tracker.update_with_rating(EventRating.GREAT)
        assert tracker.state.combo == 2

    def test_perfect_and_great_both_build_combo(self) -> None:
        tracker = SessionTracker()
        tracker.update_with_rating(EventRating.PERFECT)
        tracker.update_with_rating(EventRating.GREAT)
        tracker.update_with_rating(EventRating.PERFECT)
        assert tracker.state.combo == 3

    def test_ok_resets_combo(self) -> None:
        tracker = SessionTracker()
        tracker.update_with_rating(EventRating.PERFECT)
        tracker.update_with_rating(EventRating.GREAT)
        assert tracker.state.combo == 2
        tracker.update_with_rating(EventRating.OK)
        assert tracker.state.combo == 0

    def test_meh_resets_combo(self) -> None:
        tracker = SessionTracker()
        tracker.update_with_rating(EventRating.PERFECT)
        tracker.update_with_rating(EventRating.PERFECT)
        assert tracker.state.combo == 2
        tracker.update_with_rating(EventRating.MEH)
        assert tracker.state.combo == 0

    def test_miss_resets_combo(self) -> None:
        tracker = SessionTracker()
        tracker.update_with_rating(EventRating.GREAT)
        tracker.update_with_rating(EventRating.PERFECT)
        assert tracker.state.combo == 2
        tracker.update_with_rating(EventRating.MISS)
        assert tracker.state.combo == 0

    @pytest.mark.parametrize(
        "resetting_rating",
        [EventRating.OK, EventRating.MEH, EventRating.MISS],
    )
    def test_multiplier_resets_to_one(self, resetting_rating: EventRating) -> None:
        tracker = SessionTracker()
        # Raise multiplier above 1.0 with prior PERFECT/GREAT events.
        tracker.update_with_rating(EventRating.PERFECT)
        tracker.update_with_rating(EventRating.GREAT)
        assert tracker.state.multiplier > 1.0
        tracker.update_with_rating(resetting_rating)
        assert tracker.state.multiplier == 1.0

    def test_perfect_increases_multiplier_by_point_one(self) -> None:
        tracker = SessionTracker()
        tracker.update_with_rating(EventRating.PERFECT)
        assert tracker.state.multiplier == pytest.approx(1.10)

    def test_great_increases_multiplier_by_point_zero_five(self) -> None:
        tracker = SessionTracker()
        tracker.update_with_rating(EventRating.GREAT)
        assert tracker.state.multiplier == pytest.approx(1.05)

    def test_multiplier_capped_at_four(self) -> None:
        tracker = SessionTracker()
        # 100 PERFECTs would drive the multiplier well past 4.0 without a cap.
        for _ in range(100):
            tracker.update_with_rating(EventRating.PERFECT)
        assert tracker.state.multiplier == pytest.approx(4.0)


class TestGradeBoundaries:
    """Grade band boundaries via _calculate_grade (Requirement 5.6).

    ``_calculate_grade`` takes an accuracy float directly, so exact boundary
    values can be tested without constructing scoring sequences.

    Note: the accuracy-band method maps purely by accuracy and does NOT emit
    "SS"/"ALL PERFECT"/"FULL COMBO" labels; those states are not wired into
    SessionTracker, so they are intentionally not asserted here.
    """

    @pytest.mark.parametrize(
        ("accuracy", "expected_grade"),
        [
            (100.00, "S"),
            (99.99, "S"),
            (90.00, "S"),
            (89.99, "A"),
            (80.00, "A"),
            (79.99, "B"),
            (75.00, "B"),
            (74.99, "B"),
            (70.00, "B"),
            (69.99, "C"),
            (60.00, "C"),
            (59.99, "D"),
            (50.00, "D"),
            (49.99, "FAILED"),
            (30.00, "FAILED"),
            (29.99, "FAILED"),
            (0.00, "FAILED"),
        ],
    )
    def test_grade_band_boundaries(self, accuracy: float, expected_grade: str) -> None:
        assert SessionTracker()._calculate_grade(accuracy) == expected_grade

    def test_accuracy_is_continuous_float_in_range(self) -> None:
        # After a mixed sequence the stored accuracy is a continuous float, not a
        # value snapped to a grade category boundary.
        tracker = SessionTracker()
        for rating in (
            EventRating.PERFECT,
            EventRating.GREAT,
            EventRating.OK,
            EventRating.MEH,
            EventRating.MISS,
            EventRating.PERFECT,
        ):
            tracker.update_with_rating(rating)
        accuracy = tracker.state.accuracy_percentage
        assert isinstance(accuracy, float)
        assert 0.0 <= accuracy <= 100.0

    def test_all_perfect_session_yields_grade_s(self) -> None:
        # An all-PERFECT session earns the top S grade. Accuracy is the
        # multiplier-independent mean of per-rating quality weights, so an
        # all-PERFECT session yields exactly 100.0 (never above 100). The
        # accuracy-band method does not produce an "ALL PERFECT" label.
        tracker = SessionTracker()
        for _ in range(10):
            tracker.update_with_rating(EventRating.PERFECT)
        assert tracker.state.accuracy_percentage == pytest.approx(100.0)
        assert tracker.state.current_grade == "S"
