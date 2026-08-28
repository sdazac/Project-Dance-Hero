"""SessionTracker: manages combo tracking, multipliers, and final grading."""

from dataclasses import dataclass

from opendance.scoring.models import EventRating


@dataclass
class SessionState:
    combo: int = 0
    multiplier: float = 1.0
    total_score: float = 0.0
    max_possible_score: float = 0.0
    accuracy_percentage: float = 0.0
    current_grade: str = "FAILED"
    # Accuracy accumulators (multiplier-independent). Additive and backward
    # compatible: defaults preserve existing construction behavior.
    quality_sum: float = 0.0
    rated_events: int = 0


class SessionTracker:
    # Arcade-style points per event
    BASE_POINTS = {
        EventRating.PERFECT: 1000.0,
        EventRating.GREAT: 800.0,
        EventRating.OK: 500.0,
        EventRating.MEH: 200.0,
        EventRating.MISS: 0.0
    }

    # Single source of truth for per-rating quality weights. Derived from the
    # product.md rating band floors (PERFECT ideal 1.0, GREAT >=75% -> 0.75,
    # OK >=50% -> 0.50, MEH >=30% -> 0.30, MISS <30% -> 0.0). Accuracy is the
    # mean of these weights, which is inherently bounded to [0, 1] and thus
    # independent of the arcade combo multiplier.
    RATING_QUALITY = {
        EventRating.PERFECT: 1.00,
        EventRating.GREAT: 0.75,
        EventRating.OK: 0.50,
        EventRating.MEH: 0.30,
        EventRating.MISS: 0.00,
    }

    def __init__(self) -> None:
        self.state = SessionState()

    def update_with_rating(self, rating: EventRating) -> SessionState:
        max_pts = self.BASE_POINTS[EventRating.PERFECT]
        self.state.max_possible_score += max_pts * self.state.multiplier

        # Per product.md combo rules: only PERFECT and GREAT increase combo;
        # OK, MEH, and MISS reset combo and multiplier.
        if rating in (EventRating.PERFECT, EventRating.GREAT):
            self.state.combo += 1
            if rating == EventRating.PERFECT:
                self.state.multiplier = min(self.state.multiplier + 0.10, 4.0)
            else:  # GREAT
                self.state.multiplier = min(self.state.multiplier + 0.05, 4.0)
        else:  # OK, MEH, MISS all reset
            self.state.combo = 0
            self.state.multiplier = 1.0

        pts_gained = self.BASE_POINTS[rating] * self.state.multiplier
        self.state.total_score += pts_gained

        # Accuracy is the multiplier-independent mean of per-rating quality
        # weights (in [0, 1]), so accuracy_percentage stays within [0, 100]
        # regardless of combo streaks. This is decoupled from total_score.
        self.state.quality_sum += self.RATING_QUALITY[rating]
        self.state.rated_events += 1
        if self.state.rated_events > 0:
            self.state.accuracy_percentage = (
                self.state.quality_sum / self.state.rated_events
            ) * 100.0
        else:
            self.state.accuracy_percentage = 0.0

        self.state.current_grade = self._calculate_grade(self.state.accuracy_percentage)
        return self.state

    def _calculate_grade(self, accuracy: float) -> str:
        # Pure accuracy bands per product.md. SS (full-combo, not all-perfect)
        # requires combo/all-perfect state not available here, so the accuracy
        # band alone maps to S/A/B/C/D/FAILED. SS is reserved as the
        # full-combo/all-perfect internal label elsewhere.
        if accuracy >= 90.0:
            return "S"
        elif accuracy >= 80.0:
            return "A"
        elif accuracy >= 70.0:
            return "B"
        elif accuracy >= 60.0:
            return "C"
        elif accuracy >= 50.0:
            return "D"
        return "FAILED"
