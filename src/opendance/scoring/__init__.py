"""OpenDance AI scoring pipeline (Phase 3)."""

from opendance.scoring.aggregation import aggregate_scores
from opendance.scoring.alignment import align_frame
from opendance.scoring.angle_compare import compute_angle_score
from opendance.scoring.engine import ScoringEngine
from opendance.scoring.feedback import generate_feedback
from opendance.scoring.models import (
    LANDMARK_REGIONS,
    EventRating,
    FeedbackItem,
    FrameComparison,
)
from opendance.scoring.motion_compare import compute_motion_score
from opendance.scoring.pose_compare import compute_pose_score
from opendance.scoring.rating import compute_event_rating
from opendance.scoring.timing_compare import compute_timing_score

__all__ = [
    "EventRating",
    "FeedbackItem",
    "FrameComparison",
    "LANDMARK_REGIONS",
    "ScoringEngine",
    "aggregate_scores",
    "align_frame",
    "compute_angle_score",
    "compute_event_rating",
    "compute_motion_score",
    "compute_pose_score",
    "compute_timing_score",
    "generate_feedback",
]
