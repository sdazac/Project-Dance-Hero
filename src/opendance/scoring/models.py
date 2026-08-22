"""Scoring pipeline data models for OpenDance AI (Phase 3).

Contains:
- EventRating enum (PERFECT/GREAT/OK/MEH/MISS)
- FeedbackItem (body region, issue type, severity, description)
- FrameComparison (per-frame scoring result)
- LANDMARK_REGIONS (mapping from landmark index to body region name)
"""

from dataclasses import dataclass
from enum import Enum


class EventRating(Enum):
    """Categorical event rating derived from combined score."""

    PERFECT = "PERFECT"
    GREAT = "GREAT"
    OK = "OK"
    MEH = "MEH"
    MISS = "MISS"


@dataclass(frozen=True)
class FeedbackItem:
    """Structured feedback for a single scoring issue.

    Attributes:
        body_region: Body region name from LANDMARK_REGIONS
            (e.g., "left_arm", "torso", "right_leg").
        issue_type: Stable issue type string. One of:
            "angle_mismatch", "position_off",
            "timing_phase_mismatch", "low_confidence".
        severity: Error magnitude normalized to [0.0, 1.0].
            Angle: min(1.0, error_degrees / 90.0).
            Pose: min(1.0, landmark_distance / 0.5).
        description: Measurable, non-subjective description
            (e.g., "left elbow angle differs by 25°").
    """

    body_region: str
    issue_type: str
    severity: float
    description: str


@dataclass(frozen=True)
class FrameComparison:
    """Complete scoring result for one player frame.

    Attributes:
        timestamp_ms: Player frame timestamp.
        pose_score: [0, 100] or None if insufficient landmarks.
        angle_score: [0, 100] or None if no valid angles.
        motion_score: [0, 100] or None if no valid motion.
        timing_score: [0, 100] or None if no valid timing data.
        combined_score: [0, 100] or None if all sub-scores None.
        event_rating: PERFECT/GREAT/OK/MEH/MISS (MISS if combined None).
        feedback: Tuple of FeedbackItems for issues above significance threshold.
    """

    timestamp_ms: int
    pose_score: float | None
    angle_score: float | None
    motion_score: float | None
    timing_score: float | None
    combined_score: float | None
    event_rating: EventRating
    feedback: tuple[FeedbackItem, ...]


# Deterministic mapping from MediaPipe landmark index to body region name.
# Used by feedback generation to identify which body area has an issue.
# Regions: "face", "left_arm", "right_arm", "torso", "left_leg", "right_leg"
LANDMARK_REGIONS: dict[int, str] = {
    # Face / head (landmarks 0-10)
    0: "face",    # nose
    1: "face",    # left eye inner
    2: "face",    # left eye
    3: "face",    # left eye outer
    4: "face",    # right eye inner
    5: "face",    # right eye
    6: "face",    # right eye outer
    7: "face",    # left ear
    8: "face",    # right ear
    9: "face",    # mouth left
    10: "face",   # mouth right
    # Left arm (landmarks 11, 13, 15, 17, 19, 21)
    11: "left_arm",   # left shoulder
    13: "left_arm",   # left elbow
    15: "left_arm",   # left wrist
    17: "left_arm",   # left pinky
    19: "left_arm",   # left index
    21: "left_arm",   # left thumb
    # Right arm (landmarks 12, 14, 16, 18, 20, 22)
    12: "right_arm",  # right shoulder
    14: "right_arm",  # right elbow
    16: "right_arm",  # right wrist
    18: "right_arm",  # right pinky
    20: "right_arm",  # right index
    22: "right_arm",  # right thumb
    # Torso (landmarks 23, 24)
    23: "torso",      # left hip
    24: "torso",      # right hip
    # Left leg (landmarks 25, 27, 29, 31)
    25: "left_leg",   # left knee
    27: "left_leg",   # left ankle
    29: "left_leg",   # left heel
    31: "left_leg",   # left foot index
    # Right leg (landmarks 26, 28, 30, 32)
    26: "right_leg",  # right knee
    28: "right_leg",  # right ankle
    30: "right_leg",  # right heel
    32: "right_leg",  # right foot index
}
