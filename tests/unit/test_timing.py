"""Unit tests for the Practice Mode timer-rate helper.

Tests ``opendance.ui.timing.fps_to_interval_ms``, a pure, UI-independent
function that converts a frame rate into a safe QTimer interval. These tests
require no Qt event loop and no camera.

Covers:
- Representative fps -> interval conversions (with correct rounding).
- High-fps clamping to ``MIN_INTERVAL_MS`` (never 0 or negative).
- Invalid/non-finite fps (0, negative, NaN, +/-inf) -> ``FALLBACK_INTERVAL_MS``.
- General invariant: any positive finite fps yields an interval >= 1.
- Rounding correctness (round, not floor).

Also tests ``slider_to_ms`` and ``ms_to_slider``, the pure, UI-independent
seek-slider <-> milliseconds conversions used by the seek control. These
require no Qt event loop and no real media.
"""

import math

import pytest

from opendance.ui.timing import (
    FALLBACK_INTERVAL_MS,
    MIN_INTERVAL_MS,
    fps_to_interval_ms,
    ms_to_slider,
    slider_to_ms,
)


class TestRepresentativeValues:
    """Representative fps values map to the expected rounded interval."""

    @pytest.mark.parametrize(
        ("fps", "expected_ms"),
        [
            (30.0, 33),  # round(1000/30) = round(33.33) = 33
            (12.0, 83),  # round(1000/12) = round(83.33) = 83
            (15.0, 67),  # round(1000/15) = round(66.67) = 67
            (60.0, 17),  # round(1000/60) = round(16.67) = 17
            (24.0, 42),  # round(1000/24) = round(41.67) = 42
            (10.0, 100),  # 1000/10 = 100 exactly
        ],
    )
    def test_expected_interval(self, fps: float, expected_ms: int) -> None:
        assert fps_to_interval_ms(fps) == expected_ms


class TestRoundingCorrectness:
    """The helper uses round(), not floor()."""

    def test_uses_round_not_floor(self) -> None:
        # 1000/13 = 76.92..., round -> 77 (floor would give 76).
        assert fps_to_interval_ms(13.0) == 77
        assert fps_to_interval_ms(13.0) != int(1000 / 13.0)


class TestHighFpsClamping:
    """Very large fps clamps to MIN_INTERVAL_MS and never goes to zero."""

    def test_very_large_fps_clamps_to_min(self) -> None:
        assert fps_to_interval_ms(100_000.0) == MIN_INTERVAL_MS

    def test_clamped_interval_is_positive(self) -> None:
        interval = fps_to_interval_ms(100_000.0)
        assert interval >= MIN_INTERVAL_MS
        assert interval > 0

    def test_fps_just_above_1000_clamps_to_one(self) -> None:
        # round(1000/2000) = round(0.5) = 0, which must be clamped to 1.
        assert fps_to_interval_ms(2000.0) == MIN_INTERVAL_MS


class TestInvalidFps:
    """Non-positive or non-finite fps returns the fallback interval."""

    @pytest.mark.parametrize(
        "fps",
        [
            0.0,
            -1.0,
            -30.0,
            float("nan"),
            float("inf"),
            float("-inf"),
        ],
    )
    def test_invalid_fps_returns_fallback(self, fps: float) -> None:
        assert fps_to_interval_ms(fps) == FALLBACK_INTERVAL_MS


class TestGeneralInvariant:
    """Any positive finite fps yields an interval of at least MIN_INTERVAL_MS."""

    @pytest.mark.parametrize(
        "fps",
        [0.5, 1.0, 5.0, 12.0, 15.0, 24.0, 30.0, 60.0, 120.0, 240.0, 5000.0],
    )
    def test_positive_finite_fps_never_below_min(self, fps: float) -> None:
        interval = fps_to_interval_ms(fps)
        assert interval >= MIN_INTERVAL_MS
        assert interval > 0

    def test_constants_have_expected_values(self) -> None:
        # Guard the documented contract the callers rely on.
        assert MIN_INTERVAL_MS == 1
        assert FALLBACK_INTERVAL_MS == 1000
        assert math.isfinite(FALLBACK_INTERVAL_MS)


class TestSliderMsMapping:
    """Pure conversions between an integer seek slider and playback ms.

    Covers ``slider_to_ms`` and ``ms_to_slider``: endpoints, midpoint,
    out-of-range clamping, zero-duration / zero-max guards, and an approximate
    round-trip within one slider step.
    """

    # --- slider_to_ms -----------------------------------------------------

    def test_slider_to_ms_start_endpoint(self) -> None:
        # Slider at 0 maps to the very start (0 ms).
        assert slider_to_ms(0, 1000, 60_000) == 0

    def test_slider_to_ms_end_endpoint(self) -> None:
        # Slider at its maximum maps to the full duration.
        assert slider_to_ms(1000, 1000, 60_000) == 60_000

    def test_slider_to_ms_midpoint(self) -> None:
        # Halfway slider with an even duration maps to ~half the duration.
        assert slider_to_ms(500, 1000, 60_000) == 30_000

    @pytest.mark.parametrize(
        ("slider_value", "expected_ms"),
        [
            (-1, 0),  # below range clamps to start
            (-100, 0),
            (1001, 60_000),  # above range clamps to full duration
            (5000, 60_000),
        ],
    )
    def test_slider_to_ms_out_of_range_clamps(
        self, slider_value: int, expected_ms: int
    ) -> None:
        assert slider_to_ms(slider_value, 1000, 60_000) == expected_ms

    @pytest.mark.parametrize("slider_max", [0, -1, -1000])
    def test_slider_to_ms_zero_or_negative_max_guard(self, slider_max: int) -> None:
        assert slider_to_ms(500, slider_max, 60_000) == 0

    @pytest.mark.parametrize("duration_ms", [0, -1, -60_000])
    def test_slider_to_ms_zero_or_negative_duration_guard(
        self, duration_ms: int
    ) -> None:
        assert slider_to_ms(500, 1000, duration_ms) == 0

    # --- ms_to_slider -----------------------------------------------------

    def test_ms_to_slider_start_endpoint(self) -> None:
        # Position 0 maps to the start of the slider range.
        assert ms_to_slider(0, 60_000, 1000) == 0

    def test_ms_to_slider_end_endpoint(self) -> None:
        # Position at full duration maps to the slider maximum.
        assert ms_to_slider(60_000, 60_000, 1000) == 1000

    def test_ms_to_slider_midpoint(self) -> None:
        # Halfway position maps to ~half the slider range (round semantics).
        assert ms_to_slider(30_000, 60_000, 1000) == 500

    @pytest.mark.parametrize(
        ("position_ms", "expected_value"),
        [
            (-1, 0),  # negative position clamps to start
            (-30_000, 0),
            (60_001, 1000),  # beyond duration clamps to slider max
            (120_000, 1000),
        ],
    )
    def test_ms_to_slider_out_of_range_clamps(
        self, position_ms: int, expected_value: int
    ) -> None:
        assert ms_to_slider(position_ms, 60_000, 1000) == expected_value

    @pytest.mark.parametrize("duration_ms", [0, -1, -60_000])
    def test_ms_to_slider_zero_or_negative_duration_guard(
        self, duration_ms: int
    ) -> None:
        assert ms_to_slider(30_000, duration_ms, 1000) == 0

    @pytest.mark.parametrize("slider_max", [0, -1, -1000])
    def test_ms_to_slider_zero_or_negative_max_guard(self, slider_max: int) -> None:
        assert ms_to_slider(30_000, 60_000, slider_max) == 0

    # --- round-trip -------------------------------------------------------

    @pytest.mark.parametrize(
        ("position_ms", "duration_ms"),
        [
            (0, 60_000),
            (15_000, 60_000),
            (30_000, 60_000),
            (45_123, 60_000),
            (59_999, 60_000),
            (7_777, 200_000),
            (123_456, 200_000),
        ],
    )
    def test_round_trip_within_one_slider_step(
        self, position_ms: int, duration_ms: int
    ) -> None:
        # slider_to_ms(ms_to_slider(pos)) recovers pos within one slider step.
        # One step is duration/slider_max ms; add 1 for integer rounding slack.
        slider_max = 1000
        recovered = slider_to_ms(
            ms_to_slider(position_ms, duration_ms, slider_max),
            slider_max,
            duration_ms,
        )
        tolerance = duration_ms / slider_max + 1
        assert recovered == pytest.approx(position_ms, abs=tolerance)
