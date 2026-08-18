"""Unit tests for FPSMonitor rolling-window measurement.

Property 8: FPS rolling window reflects recent frame rate.
- fps == (window_count - 1) / (newest - oldest) for any valid timestamp sequence
- Returns 0.0 with fewer than 2 timestamps
- reset() clears state
- Rolling window discards old timestamps beyond window_size
"""

from hypothesis import given, settings
from hypothesis.strategies import floats, integers, lists

from opendance.camera.fps_monitor import FPSMonitor


class TestFPSMonitorBasic:
    """Basic behavior tests."""

    def test_initial_fps_is_zero(self) -> None:
        monitor = FPSMonitor()
        assert monitor.fps == 0.0

    def test_single_tick_fps_is_zero(self) -> None:
        monitor = FPSMonitor()
        monitor.tick()
        assert monitor.fps == 0.0

    def test_two_ticks_produces_nonzero_fps(self) -> None:
        monitor = FPSMonitor(window_size=30)
        monitor._timestamps.append(0.0)
        monitor._timestamps.append(1.0)
        # (2 - 1) / (1.0 - 0.0) = 1.0
        assert monitor.fps == 1.0

    def test_reset_clears_timestamps(self) -> None:
        monitor = FPSMonitor()
        monitor.tick()
        monitor.tick()
        assert monitor.fps > 0.0
        monitor.reset()
        assert monitor.fps == 0.0

    def test_rolling_window_discards_old(self) -> None:
        monitor = FPSMonitor(window_size=5)
        # Add 10 timestamps (only last 5 kept)
        for i in range(10):
            monitor._timestamps.append(float(i))
        assert len(monitor._timestamps) == 5
        # timestamps are [5, 6, 7, 8, 9]
        # fps = (5 - 1) / (9 - 5) = 4 / 4 = 1.0
        assert monitor.fps == 1.0


class TestFPSMonitorCalculation:
    """Test FPS calculation matches the design formula."""

    def test_known_30fps_sequence(self) -> None:
        """30 frames at 1/30 second intervals → fps ≈ 30."""
        monitor = FPSMonitor(window_size=30)
        interval = 1.0 / 30.0
        for i in range(30):
            monitor._timestamps.append(i * interval)
        expected = (30 - 1) / (29 * interval)
        assert abs(monitor.fps - expected) < 0.001

    def test_known_60fps_sequence(self) -> None:
        """60 frames at 1/60 second intervals → fps ≈ 60."""
        monitor = FPSMonitor(window_size=60)
        interval = 1.0 / 60.0
        for i in range(60):
            monitor._timestamps.append(i * interval)
        expected = (60 - 1) / (59 * interval)
        assert abs(monitor.fps - expected) < 0.001

    def test_identical_timestamps_returns_zero(self) -> None:
        """If all timestamps are identical (elapsed=0), fps is 0.0."""
        monitor = FPSMonitor(window_size=5)
        for _ in range(5):
            monitor._timestamps.append(1.0)
        assert monitor.fps == 0.0

    def test_formula_with_custom_window(self) -> None:
        """Verify formula: fps = (count - 1) / (newest - oldest)."""
        monitor = FPSMonitor(window_size=10)
        # 10 timestamps: 0.0, 0.1, 0.2, ..., 0.9
        for i in range(10):
            monitor._timestamps.append(i * 0.1)
        # fps = (10 - 1) / (0.9 - 0.0) = 9 / 0.9 = 10.0
        assert abs(monitor.fps - 10.0) < 0.001


class TestFPSMonitorProperty:
    """Property-based tests using hypothesis."""

    @given(
        timestamps=lists(
            floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=50,
        )
    )
    @settings(max_examples=100)
    def test_fps_formula_holds_for_monotonic_sequences(
        self, timestamps: list[float]
    ) -> None:
        """For any monotonically increasing sequence, fps matches formula."""
        # Sort to make monotonic
        timestamps = sorted(timestamps)
        elapsed = timestamps[-1] - timestamps[0]
        if elapsed < 1e-9:
            return  # Skip degenerate case (timestamps too close or identical)

        window_size = len(timestamps)
        monitor = FPSMonitor(window_size=window_size)
        for t in timestamps:
            monitor._timestamps.append(t)

        expected = (len(timestamps) - 1) / elapsed
        assert abs(monitor.fps - expected) < 0.0001

    @given(window_size=integers(min_value=2, max_value=100))
    @settings(max_examples=50)
    def test_reset_always_returns_zero(self, window_size: int) -> None:
        """After reset, fps is always 0.0 regardless of previous state."""
        monitor = FPSMonitor(window_size=window_size)
        # Add some ticks
        for i in range(window_size):
            monitor._timestamps.append(float(i))
        monitor.reset()
        assert monitor.fps == 0.0
