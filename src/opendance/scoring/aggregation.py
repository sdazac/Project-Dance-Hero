"""Score aggregation: weighted average with renormalization for missing data.

Uses existing ScoringWeights (pose=0.40, angle=0.25, motion=0.20, timing=0.15).
Does NOT duplicate or redefine the weights. Consumes them directly.
"""

from opendance.config.models import ScoringWeights


def aggregate_scores(
    pose_score: float | None,
    angle_score: float | None,
    motion_score: float | None,
    timing_score: float | None,
    weights: ScoringWeights,
) -> float | None:
    """Weighted average of available sub-scores with weight renormalization.

    Formula:
        available = [(weight, score) for each non-None score]
        if not available: return None
        total_weight = sum(weight for weight, _ in available)
        combined = sum(weight * score for weight, score in available) / total_weight

    None scores are excluded entirely (not treated as zero).
    Remaining weights are renormalized to sum to 1.0.
    Result is always in [0.0, 100.0] or None.

    Args:
        pose_score: PoseScore [0, 100] or None.
        angle_score: AngleScore [0, 100] or None.
        motion_score: MotionScore [0, 100] or None.
        timing_score: TimingScore [0, 100] or None.
        weights: ScoringWeights from configuration.

    Returns:
        CombinedScore in [0.0, 100.0], or None if all sub-scores are None.
    """
    pairs: list[tuple[float, float]] = []

    if pose_score is not None:
        pairs.append((weights.pose_similarity, pose_score))
    if angle_score is not None:
        pairs.append((weights.angle_similarity, angle_score))
    if motion_score is not None:
        pairs.append((weights.motion_similarity, motion_score))
    if timing_score is not None:
        pairs.append((weights.timing_similarity, timing_score))

    if not pairs:
        return None

    total_weight = sum(w for w, _ in pairs)
    if total_weight <= 0.0:
        return None

    combined = sum(w * s for w, s in pairs) / total_weight
    return max(0.0, min(100.0, combined))
