"""Event rating: classify combined score into PERFECT/GREAT/OK/MEH/MISS.

Uses existing ScoringThresholds directly. Does NOT duplicate thresholds.
"""

from opendance.config.models import ScoringThresholds
from opendance.scoring.models import EventRating


def compute_event_rating(
    combined_score: float | None,
    thresholds: ScoringThresholds,
) -> EventRating:
    """Map combined score to categorical event rating.

    None → MISS
    >= perfect_min (90) → PERFECT
    >= great_min (75) → GREAT
    >= ok_min (50) → OK
    >= meh_min (30) → MEH
    < meh_min → MISS

    Args:
        combined_score: CombinedScore [0, 100] or None.
        thresholds: ScoringThresholds from configuration.

    Returns:
        EventRating enum value.
    """
    if combined_score is None:
        return EventRating.MISS

    if combined_score >= thresholds.perfect_min:
        return EventRating.PERFECT
    if combined_score >= thresholds.great_min:
        return EventRating.GREAT
    if combined_score >= thresholds.ok_min:
        return EventRating.OK
    if combined_score >= thresholds.meh_min:
        return EventRating.MEH
    return EventRating.MISS
