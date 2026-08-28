"""Bug-condition exploration test for SessionTracker accuracy bounds.

This module encodes Correctness Property P1 from the scoring-accuracy-fix design:

    P1 (bounded): for any finite sequence of ratings,
    ``0.0 <= accuracy_percentage <= 100.0``.

These tests are EXPECTED TO FAIL on the current (unfixed) code. The bug is that
``max_possible_score`` accrues with the pre-bump multiplier while ``total_score``
uses the post-bump multiplier for PERFECT/GREAT events, so ``accuracy_percentage``
can exceed 100% during PERFECT/GREAT streaks. The failure of these tests confirms
the bug exists; after the fix (later tasks) they must pass unchanged.

Pure tests: no Qt event loop, no camera, no MediaPipe.

Validates: Requirements 1.1
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from opendance.scoring.models import EventRating
from opendance.scoring.session_tracker import SessionTracker


@given(st.lists(st.sampled_from(list(EventRating)), min_size=1, max_size=100))
def test_accuracy_percentage_is_bounded(ratings: list[EventRating]) -> None:
    """P1: accuracy stays within [0, 100] for any rating sequence."""
    tracker = SessionTracker()
    for rating in ratings:
        tracker.update_with_rating(rating)
    accuracy = tracker.state.accuracy_percentage
    assert 0.0 <= accuracy <= 100.0


def test_all_perfect_stays_within_bounds() -> None:
    """An all-PERFECT streak must keep accuracy at or below 100.0.

    Explicit witness of the bug: a PERFECT streak drives accuracy above 100 on
    the unfixed code. Post-fix, an all-PERFECT session yields exactly 100.0.
    """
    tracker = SessionTracker()
    for _ in range(10):
        tracker.update_with_rating(EventRating.PERFECT)
    assert 0.0 <= tracker.state.accuracy_percentage <= 100.0


# ---------------------------------------------------------------------------
# Task 4.1 - Endpoint and mean-semantics unit tests
# ---------------------------------------------------------------------------


class TestAccuracyMeanSemantics:
    """Accuracy equals the mean per-rating quality weight x100 (Req 1.2-1.5, 2.1).

    These example-based tests pin the endpoint and mean semantics of the
    corrected, multiplier-independent accuracy computation.
    """

    def test_all_perfect_yields_one_hundred(self) -> None:
        """Ten PERFECT events -> mean quality 1.0 -> accuracy 100.0 (Req 1.2)."""
        tracker = SessionTracker()
        for _ in range(10):
            tracker.update_with_rating(EventRating.PERFECT)
        assert tracker.state.accuracy_percentage == pytest.approx(100.0)

    def test_all_miss_yields_zero(self) -> None:
        """Five MISS events -> mean quality 0.0 -> accuracy 0.0 (Req 1.3)."""
        tracker = SessionTracker()
        for _ in range(5):
            tracker.update_with_rating(EventRating.MISS)
        assert tracker.state.accuracy_percentage == pytest.approx(0.0)

    def test_perfect_and_miss_average_to_fifty(self) -> None:
        """[PERFECT, MISS] -> mean (1.0 + 0.0)/2 -> accuracy 50.0 (Req 1.4)."""
        tracker = SessionTracker()
        tracker.update_with_rating(EventRating.PERFECT)
        tracker.update_with_rating(EventRating.MISS)
        assert tracker.state.accuracy_percentage == pytest.approx(50.0)

    def test_two_greats_average_to_seventy_five(self) -> None:
        """[GREAT, GREAT] -> mean 0.75 -> accuracy 75.0 (Req 1.4)."""
        tracker = SessionTracker()
        tracker.update_with_rating(EventRating.GREAT)
        tracker.update_with_rating(EventRating.GREAT)
        assert tracker.state.accuracy_percentage == pytest.approx(75.0)

    def test_ok_and_meh_average_to_forty(self) -> None:
        """[OK, MEH] -> mean (0.50 + 0.30)/2 -> accuracy 40.0 (Req 1.4)."""
        tracker = SessionTracker()
        tracker.update_with_rating(EventRating.OK)
        tracker.update_with_rating(EventRating.MEH)
        assert tracker.state.accuracy_percentage == pytest.approx(40.0)

    def test_empty_session_is_zero(self) -> None:
        """No scored events -> accuracy_percentage is 0.0 (Req 1.5)."""
        tracker = SessionTracker()
        assert tracker.state.accuracy_percentage == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Task 4.2 - Property tests P2 / P3 / P4
# ---------------------------------------------------------------------------


@given(st.lists(st.sampled_from(list(EventRating)), min_size=1, max_size=50))
def test_accuracy_is_order_independent(ratings: list[EventRating]) -> None:
    """P2: permuting the ratings does not change final accuracy (Req 1.4)."""
    original = SessionTracker()
    for rating in ratings:
        original.update_with_rating(rating)

    permuted = SessionTracker()
    for rating in sorted(ratings, key=lambda r: r.name):
        permuted.update_with_rating(rating)

    assert permuted.state.accuracy_percentage == pytest.approx(
        original.state.accuracy_percentage
    )


@given(st.integers(min_value=1, max_value=50))
def test_endpoint_streaks(n: int) -> None:
    """P3: all-PERFECT -> 100.0 and all-MISS -> 0.0 for any length (Req 1.2, 1.3)."""
    perfect = SessionTracker()
    miss = SessionTracker()
    for _ in range(n):
        perfect.update_with_rating(EventRating.PERFECT)
        miss.update_with_rating(EventRating.MISS)
    assert perfect.state.accuracy_percentage == pytest.approx(100.0)
    assert miss.state.accuracy_percentage == pytest.approx(0.0)


@given(st.lists(st.sampled_from(list(EventRating)), min_size=1, max_size=50))
def test_accuracy_equals_quality_mean(ratings: list[EventRating]) -> None:
    """P4: accuracy == mean(RATING_QUALITY[r]) * 100 over inputs (Req 1.4)."""
    tracker = SessionTracker()
    for rating in ratings:
        tracker.update_with_rating(rating)

    expected = (
        sum(SessionTracker.RATING_QUALITY[r] for r in ratings) / len(ratings)
    ) * 100.0
    assert tracker.state.accuracy_percentage == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Task 4.3 - Preserve combo / multiplier / score regression tests
# ---------------------------------------------------------------------------


class TestArcadePathPreserved:
    """Combo, multiplier, and arcade score are unchanged by the fix (Req 3.1-3.3)."""

    def test_combo_increments_on_perfect_and_great(self) -> None:
        tracker = SessionTracker()
        tracker.update_with_rating(EventRating.PERFECT)
        tracker.update_with_rating(EventRating.GREAT)
        tracker.update_with_rating(EventRating.PERFECT)
        assert tracker.state.combo == 3

    @pytest.mark.parametrize(
        "resetting_rating",
        [EventRating.OK, EventRating.MEH, EventRating.MISS],
    )
    def test_combo_resets_on_ok_meh_miss(
        self, resetting_rating: EventRating
    ) -> None:
        tracker = SessionTracker()
        tracker.update_with_rating(EventRating.PERFECT)
        tracker.update_with_rating(EventRating.PERFECT)
        assert tracker.state.combo == 2
        tracker.update_with_rating(resetting_rating)
        assert tracker.state.combo == 0

    def test_multiplier_increments_by_documented_amounts(self) -> None:
        perfect = SessionTracker()
        perfect.update_with_rating(EventRating.PERFECT)
        assert perfect.state.multiplier == pytest.approx(1.10)

        great = SessionTracker()
        great.update_with_rating(EventRating.GREAT)
        assert great.state.multiplier == pytest.approx(1.05)

    def test_multiplier_caps_at_four(self) -> None:
        tracker = SessionTracker()
        for _ in range(100):
            tracker.update_with_rating(EventRating.PERFECT)
        assert tracker.state.multiplier == pytest.approx(4.0)

    def test_total_score_grows_with_multiplier(self) -> None:
        """Consecutive PERFECTs yield strictly increasing score increments.

        The arcade score path scales BASE_POINTS by the rising multiplier, so
        each PERFECT after the first adds more than the previous one did.
        """
        tracker = SessionTracker()
        increments: list[float] = []
        previous_total = tracker.state.total_score
        for _ in range(5):
            tracker.update_with_rating(EventRating.PERFECT)
            increments.append(tracker.state.total_score - previous_total)
            previous_total = tracker.state.total_score

        # Each successive increment is larger than the last (multiplier rising).
        assert all(
            increments[i] < increments[i + 1] for i in range(len(increments) - 1)
        )
        # And the multiplier-scaled total exceeds the un-multiplied base sum.
        base_points = SessionTracker.BASE_POINTS[EventRating.PERFECT]
        assert tracker.state.total_score > base_points * 5
