"""Unit tests for temporal alignment (nearest-frame).

Tests align_frame() with various timestamp/duration/frame-count combinations.
"""

from opendance.scoring.alignment import align_frame


class TestAlignmentBasic:
    """Basic alignment behavior."""

    def test_timestamp_zero_maps_to_frame_zero(self) -> None:
        assert align_frame(0, 1000, 10) == 0

    def test_timestamp_at_duration_maps_to_last_frame(self) -> None:
        assert align_frame(1000, 1000, 10) == 9

    def test_midpoint_timestamp(self) -> None:
        # 500/1000 = 0.5, exact = 0.5 * 9 = 4.5, round = 4 (Python rounds .5 to even)
        result = align_frame(500, 1000, 10)
        assert result == 4 or result == 5  # banker's rounding

    def test_quarter_timestamp(self) -> None:
        # 250/1000 = 0.25, exact = 0.25 * 9 = 2.25, round = 2
        assert align_frame(250, 1000, 10) == 2

    def test_three_quarter_timestamp(self) -> None:
        # 750/1000 = 0.75, exact = 0.75 * 9 = 6.75, round = 7
        assert align_frame(750, 1000, 10) == 7


class TestAlignmentBoundaries:
    """Boundary and edge cases."""

    def test_negative_timestamp_clamps_to_zero(self) -> None:
        assert align_frame(-100, 1000, 10) == 0

    def test_timestamp_beyond_duration_clamps_to_last(self) -> None:
        assert align_frame(2000, 1000, 10) == 9

    def test_single_frame_reference(self) -> None:
        assert align_frame(500, 1000, 1) == 0

    def test_zero_duration_returns_zero(self) -> None:
        assert align_frame(500, 0, 10) == 0

    def test_zero_frame_count_returns_zero(self) -> None:
        assert align_frame(500, 1000, 0) == 0

    def test_two_frames(self) -> None:
        # ratio=0.3, exact=0.3*1=0.3, round=0
        assert align_frame(300, 1000, 2) == 0
        # ratio=0.7, exact=0.7*1=0.7, round=1
        assert align_frame(700, 1000, 2) == 1


class TestAlignmentDeterminism:
    """Deterministic repeated calls."""

    def test_same_input_same_output(self) -> None:
        r1 = align_frame(450, 3333, 100)
        r2 = align_frame(450, 3333, 100)
        assert r1 == r2

    def test_known_value(self) -> None:
        # 450/3333 ≈ 0.135, exact = 0.135 * 99 ≈ 13.36, round = 13
        assert align_frame(450, 3333, 100) == 13


class TestAlignmentExactFramePositions:
    """Exact frame positions map correctly."""

    def test_each_frame_in_10_frame_sequence(self) -> None:
        """For a 10-frame reference at 1000ms, frames are at 0,111,222,...,1000."""
        for i in range(10):
            ts = int(i * 1000 / 9)  # exact frame timestamp
            result = align_frame(ts, 1000, 10)
            assert result == i, f"Frame {i} at ts={ts} mapped to {result}"
