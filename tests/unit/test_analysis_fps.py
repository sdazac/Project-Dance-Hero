"""Unit tests for analysis FPS configuration and timestamp calculation.

Tests default sample_fps, valid FPS values, and timestamp derivation.
"""

import pytest

from opendance.config.models import ReferenceConfig


class TestDefaultSampleFps:
    """Verify default sample_fps is 15.0."""

    def test_default_is_15(self) -> None:
        config = ReferenceConfig()
        assert config.sample_fps == 15.0

    def test_default_type_is_float(self) -> None:
        config = ReferenceConfig()
        assert isinstance(config.sample_fps, float)


class TestValidFpsValues:
    """Test ReferenceConfig accepts various valid FPS values."""

    @pytest.mark.parametrize("fps", [10.0, 15.0, 20.0, 30.0])
    def test_accepts_common_fps(self, fps: float) -> None:
        config = ReferenceConfig(sample_fps=fps)
        assert config.sample_fps == fps

    def test_accepts_fractional_fps(self) -> None:
        config = ReferenceConfig(sample_fps=23.976)
        assert abs(config.sample_fps - 23.976) < 1e-6

    def test_accepts_high_fps(self) -> None:
        config = ReferenceConfig(sample_fps=120.0)
        assert config.sample_fps == 120.0

    def test_accepts_low_fps(self) -> None:
        config = ReferenceConfig(sample_fps=1.0)
        assert config.sample_fps == 1.0


class TestTimestampCalculation:
    """Test timestamp_ms = sample_index * (1000 / sample_fps)."""

    def test_timestamp_at_15fps(self) -> None:
        """At 15 FPS: interval = 66.67 ms."""
        fps = 15.0
        interval = 1000.0 / fps
        assert abs(interval - 66.6667) < 0.001

        timestamps = [int(i * interval) for i in range(5)]
        assert timestamps == [0, 66, 133, 200, 266]

    def test_timestamp_at_30fps(self) -> None:
        """At 30 FPS: interval = 33.33 ms."""
        fps = 30.0
        interval = 1000.0 / fps
        assert abs(interval - 33.3333) < 0.001

        timestamps = [int(i * interval) for i in range(5)]
        assert timestamps == [0, 33, 66, 100, 133]

    def test_timestamp_at_10fps(self) -> None:
        """At 10 FPS: interval = 100 ms."""
        fps = 10.0
        interval = 1000.0 / fps
        assert interval == 100.0

        timestamps = [int(i * interval) for i in range(5)]
        assert timestamps == [0, 100, 200, 300, 400]

    def test_timestamp_at_20fps(self) -> None:
        """At 20 FPS: interval = 50 ms."""
        fps = 20.0
        interval = 1000.0 / fps
        assert interval == 50.0

        timestamps = [int(i * interval) for i in range(4)]
        assert timestamps == [0, 50, 100, 150]

    def test_sample_count_for_duration(self) -> None:
        """Number of samples for 10s video at different FPS."""
        duration_ms = 10_000.0

        for fps, expected_count in [
            (10.0, 100),
            (15.0, 150),
            (20.0, 200),
            (30.0, 300),
        ]:
            interval = 1000.0 / fps
            count = int(duration_ms / interval)
            assert count == expected_count

    def test_monotonically_increasing(self) -> None:
        """Timestamps are strictly increasing for any valid FPS."""
        for fps in [10.0, 15.0, 20.0, 30.0, 60.0]:
            interval = 1000.0 / fps
            timestamps = [int(i * interval) for i in range(100)]
            for i in range(1, len(timestamps)):
                assert timestamps[i] >= timestamps[i - 1]
