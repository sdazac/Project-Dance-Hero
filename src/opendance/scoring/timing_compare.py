"""Timing comparison: movement-phase alignment metric.

Determines whether the player and reference are in the same movement phase
(both moving or both still) at the aligned frame. This is conceptually
distinct from motion comparison:

- Motion: How well do speed and direction match?
- Timing: Are both in the same movement phase (moving vs still)?

Does NOT implement peak detection, temporal windows, DTW, or
millisecond timing offsets. Phase-alignment only.
"""

from opendance.motion.motion_result import MotionFeatures


def compute_timing_score(
    player_motion: MotionFeatures | None,
    reference_motion: MotionFeatures | None,
    timing_scale: float = 0.5,
    velocity_threshold: float = 0.01,
) -> float | None:
    """Movement-phase alignment: same state = credit, mismatch = penalty.

    Per-landmark formula:
        player_moving = player_speed > velocity_threshold
        ref_moving = ref_speed > velocity_threshold

        if player_moving == ref_moving:
            per_lm = 100.0  # same phase (both moving or both still)
        else:
            moving_speed = player_speed if player_moving else ref_speed
            per_lm = max(0.0, 100.0 - moving_speed * timing_scale * 1000.0)

    timing_score = mean(per_lm across valid landmarks)  [0, 100]
    Returns None if no valid data.

    Args:
        player_motion: Player's MotionFeatures, or None.
        reference_motion: Reference MotionFeatures at aligned frame, or None.
        timing_scale: Controls penalty magnitude (default 0.5).
            Higher = more aggressive penalty for phase mismatch.
        velocity_threshold: Speed below this is considered "still" (default 0.01).
            Uses the same threshold as MotionConfig.min_velocity_threshold.

    Returns:
        TimingScore in [0.0, 100.0], or None if insufficient data.
    """
    if player_motion is None or reference_motion is None:
        return None

    p_motions = player_motion.landmark_motions
    r_motions = reference_motion.landmark_motions

    per_landmark_scores: list[float] = []
    count = min(len(p_motions), len(r_motions))

    for i in range(count):
        p_lm = p_motions[i]
        r_lm = r_motions[i]

        if p_lm is None or r_lm is None:
            continue

        p_speed = p_lm.speed
        r_speed = r_lm.speed

        if p_speed is None or r_speed is None:
            continue

        player_moving = p_speed > velocity_threshold
        ref_moving = r_speed > velocity_threshold

        if player_moving == ref_moving:
            # Same phase: full credit
            per_landmark_scores.append(100.0)
        else:
            # Phase mismatch: penalty proportional to the moving side's speed
            moving_speed = p_speed if player_moving else r_speed
            penalty = moving_speed * timing_scale * 1000.0
            per_lm_score = max(0.0, 100.0 - penalty)
            per_landmark_scores.append(per_lm_score)

    if len(per_landmark_scores) == 0:
        return None

    return sum(per_landmark_scores) / len(per_landmark_scores)
