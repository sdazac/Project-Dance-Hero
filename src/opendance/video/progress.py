"""Pure analysis-progress percentage math for the reference-video pipeline.

This module maps a ``(processed, total)`` pair of sample counts to an integer
percentage for the analysis progress bar. It is deliberately pure and
UI-independent (no Qt, no OpenCV, no I/O), so the percentage logic can be
unit-tested in isolation from the analyzer and the widgets that consume it.
"""

from __future__ import annotations


def progress_percent(done: int, total: int) -> int:
    """Map processed/total sample counts to an integer percent in [0, 100].

    A ``total`` of zero or less yields ``0`` (nothing to do / unknown), and
    ``done`` is clamped into ``[0, total]`` before the percentage is computed so
    the result is always non-negative, at most ``100``, and non-decreasing as
    ``done`` increases.
    """
    if total <= 0:
        return 0
    pct = int((max(0, min(done, total)) / total) * 100)
    return max(0, min(pct, 100))
