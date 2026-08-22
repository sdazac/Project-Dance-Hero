"""FPS measurement using a rolling window of timestamps."""

import time
from collections import deque


class FPSMonitor:
    """Measures actual frame acquisition rate using a rolling window.

    Uses a fixed-size deque of timestamps. FPS = (window_size - 1) / (newest - oldest).
    """

    def __init__(self, window_size: int = 30) -> None:
        self._timestamps: deque[float] = deque(maxlen=window_size)

    def tick(self) -> None:
        """Record a frame acquisition timestamp."""
        self._timestamps.append(time.perf_counter())

    @property
    def fps(self) -> float:
        """Return current FPS based on rolling window. Returns 0.0 if insufficient data."""
        if len(self._timestamps) < 2:
            return 0.0
        elapsed = self._timestamps[-1] - self._timestamps[0]
        if elapsed <= 0.0:
            return 0.0
        return (len(self._timestamps) - 1) / elapsed

    def reset(self) -> None:
        """Clear all timestamps."""
        self._timestamps.clear()
