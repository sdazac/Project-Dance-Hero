"""Unit tests for the pure analysis-progress percentage helper.

Tests progress_percent(done, total) which maps processed/total sample counts
to an integer percent in [0, 100]:
- total <= 0 → 0 (nothing to do / unknown)
- done clamped into [0, total] before the percentage is computed
- result is non-negative, at most 100, and non-decreasing as done increases

No Qt / OpenCV / I/O — the mapping is a pure integer function.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from opendance.video.progress import progress_percent


class TestNonPositiveTotal:
    """A total of zero or less yields 0 (nothing to do / unknown)."""

    @pytest.mark.parametrize("total", [0, -5])
    def test_returns_zero(self, total: int) -> None:
        assert progress_percent(100, total) == 0

    def test_zero_total_zero_done(self) -> None:
        assert progress_percent(0, 0) == 0


class TestBoundaries:
    """Endpoints and out-of-range done values clamp to [0, 100]."""

    def test_done_zero_is_zero(self) -> None:
        assert progress_percent(0, 100) == 0

    def test_done_equals_total_is_100(self) -> None:
        assert progress_percent(50, 50) == 100

    def test_done_greater_than_total_clamps_to_100(self) -> None:
        assert progress_percent(150, 100) == 100

    def test_negative_done_clamps_to_zero(self) -> None:
        assert progress_percent(-10, 100) == 0


class TestMidpoints:
    """Interior values use integer truncation of the fraction * 100."""

    @pytest.mark.parametrize(
        ("done", "total", "expected"),
        [
            (50, 100, 50),
            (1, 3, 33),
            (2, 3, 66),
        ],
    )
    def test_midpoint(self, done: int, total: int, expected: int) -> None:
        assert progress_percent(done, total) == expected


class TestNonDecreasing:
    """For a fixed total, percent is non-decreasing and ends at 100."""

    @pytest.mark.parametrize("total", [1, 3, 7, 100, 999])
    def test_sequence_is_non_decreasing_ending_at_100(self, total: int) -> None:
        percents = [progress_percent(done, total) for done in range(total + 1)]
        assert percents[0] == 0
        assert percents[-1] == 100
        for prev, curr in zip(percents, percents[1:]):
            assert curr >= prev


class TestProperties:
    """Universal properties across arbitrary inputs.

    Validates: Requirements 5.3
    """

    @given(done=st.integers(), total=st.integers())
    def test_result_always_in_range(self, done: int, total: int) -> None:
        assert 0 <= progress_percent(done, total) <= 100

    @given(
        done=st.integers(min_value=-1000, max_value=2000),
        total=st.integers(min_value=1, max_value=2000),
    )
    def test_monotonic_in_done(self, done: int, total: int) -> None:
        assert progress_percent(done, total) <= progress_percent(done + 1, total)

    @given(total=st.integers(max_value=0))
    def test_non_positive_total_is_zero(self, total: int) -> None:
        assert progress_percent(100, total) == 0
