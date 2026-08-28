"""Timer-rate helpers for Practice Mode.

Practice Mode drives two independent QTimers (render and scoring) whose intervals
are derived from configured frame rates (``render_fps``, ``scoring_fps``). Qt
timers require a non-negative interval and a zero interval fires as fast as the
event loop allows, which would defeat rate limiting. This module converts an fps
value into a safe millisecond interval, clamping defensively so that invalid or
extreme fps (0, negative, NaN, or very large) can never produce a zero or
negative interval.

The helper is intentionally pure and UI-independent (it does not import PySide6)
so it can be unit-tested without a Qt event loop.
"""

import math

# Smallest interval we will ever hand to a timer. One millisecond keeps the timer
# strictly periodic even for absurdly high fps values.
MIN_INTERVAL_MS = 1

# Fallback interval used when fps is not a usable positive number (0, negative,
# NaN, or infinity). ~1 FPS is slow but keeps the timer alive and recoverable.
FALLBACK_INTERVAL_MS = 1000


def fps_to_interval_ms(fps: float) -> int:
    """Convert a frame rate in fps to a QTimer interval in milliseconds.

    Returns ``round(1000 / fps)`` clamped to at least ``MIN_INTERVAL_MS``. For
    non-positive or non-finite fps the function returns ``FALLBACK_INTERVAL_MS``
    instead of dividing by zero or producing a negative interval.

    Args:
        fps: Desired frames per second.

    Returns:
        A positive interval in milliseconds (always >= ``MIN_INTERVAL_MS``).
    """
    if not math.isfinite(fps) or fps <= 0:
        return FALLBACK_INTERVAL_MS

    interval_ms = int(round(1000 / fps))
    return max(interval_ms, MIN_INTERVAL_MS)


def slider_to_ms(slider_value: int, slider_max: int, duration_ms: int) -> int:
    """Map an integer slider value in ``[0, slider_max]`` to a position in ms.

    The seek slider uses a fixed integer resolution while media positions are in
    milliseconds. This converts a slider value into the corresponding playback
    position by linear interpolation against the media duration. The slider value
    is clamped into range so out-of-bounds input can never produce a position
    outside ``[0, duration_ms]``.

    Args:
        slider_value: Current slider value.
        slider_max: Maximum slider value (the slider range upper bound).
        duration_ms: Total media duration in milliseconds.

    Returns:
        The playback position in milliseconds, or ``0`` when the slider range or
        duration is not usable (``slider_max <= 0`` or ``duration_ms <= 0``).
    """
    if slider_max <= 0 or duration_ms <= 0:
        return 0
    frac = max(0, min(slider_value, slider_max)) / slider_max
    return int(frac * duration_ms)


def ms_to_slider(position_ms: int, duration_ms: int, slider_max: int) -> int:
    """Map a position in ms to an integer slider value in ``[0, slider_max]``.

    Inverse of :func:`slider_to_ms`: converts a playback position into the slider
    value that represents it. The position is clamped into ``[0, duration_ms]``
    so out-of-bounds input can never produce a slider value outside the range.

    Args:
        position_ms: Current playback position in milliseconds.
        duration_ms: Total media duration in milliseconds.
        slider_max: Maximum slider value (the slider range upper bound).

    Returns:
        The slider value, or ``0`` when the duration or slider range is not
        usable (``duration_ms <= 0`` or ``slider_max <= 0``).
    """
    if duration_ms <= 0 or slider_max <= 0:
        return 0
    frac = max(0, min(position_ms, duration_ms)) / duration_ms
    return int(round(frac * slider_max))
