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
    current_grade: str = "F"


class SessionTracker:
    # Arcade-style points per event
    BASE_POINTS = {
        EventRating.PERFECT: 1000.0,
        EventRating.GREAT: 800.0,
        EventRating.OK: 500.0,
        EventRating.MEH: 200.0,
        EventRating.MISS: 0.0
    }

    def __init__(self) -> None:
        self.state = SessionState()

    def update_with_rating(self, rating: EventRating) -> SessionState:
        max_pts = self.BASE_POINTS[EventRating.PERFECT]
        self.state.max_possible_score += max_pts * self.state.multiplier

        if rating in (EventRating.PERFECT, EventRating.GREAT, EventRating.OK):
            self.state.combo += 1
            if rating == EventRating.PERFECT:
                self.state.multiplier = min(self.state.multiplier + 0.10, 4.0)
            elif rating == EventRating.GREAT:
                self.state.multiplier = min(self.state.multiplier + 0.05, 4.0)
        else:
            self.state.combo = 0
            self.state.multiplier = 1.0

        pts_gained = self.BASE_POINTS[rating] * self.state.multiplier
        self.state.total_score += pts_gained

        if self.state.max_possible_score > 0:
            ratio = self.state.total_score / self.state.max_possible_score
            self.state.accuracy_percentage = ratio * 100.0

        self.state.current_grade = self._calculate_grade(self.state.accuracy_percentage)
        return self.state

    def _calculate_grade(self, accuracy: float) -> str:
        if accuracy >= 100.0:
            return "SS"
        elif accuracy >= 90.0:
            return "S"
        elif accuracy >= 80.0:
            return "A"
        elif accuracy >= 70.0:
            return "B"
        elif accuracy >= 60.0:
            return "C"
        elif accuracy >= 50.0:
            return "D"
        return "F"
