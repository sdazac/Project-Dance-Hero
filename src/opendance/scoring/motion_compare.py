"""Motion comparison: speed magnitude + clamped direction dot product.

Compares player and reference MotionFeatures at an aligned frame.
Uses speed similarity and direction similarity (dot product clamped [0,1]).
Acceleration is NOT used in Phase 3 scoring.
"""

from opendance.motion.motion_result import MotionFeatures


def compute_motion_score(
    player_motion: MotionFeatures | None,
    reference_motion: MotionFeatures | None,
    speed_weight: float = 0.5,
    direction_weight: float = 0.5,
    epsilon: float = 0.001,
) -> float | None:
    """Compare speed magnitude and direction between player and reference.

    Per-landmark formula:
        If both speeds < epsilon: speed_sim = 1.0 (both still).
        Else: speed_sim = 1.0 - abs(p_speed - r_speed) / max(p_speed, r_speed, epsilon)

        If either speed < epsilon: direction undefined → use speed_sim only.
        Else: dir_sim = max(0.0, dot(p_dir, r_dir))  [clamped 0,1]
              per_lm = speed_sim * speed_weight + dir_sim * direction_weight

    score = mean(per_lm across valid landmarks) * 100.0  [0, 100]
    Returns None if no valid landmark motion pairs exist.

    Acceleration is NOT used in Phase 3 motion scoring.

    Args:
        player_motion: Player's MotionFeatures for the current frame, or None.
        reference_motion: Reference MotionFeatures at aligned frame, or None.
        speed_weight: Weight for speed similarity (default 0.5).
        direction_weight: Weight for direction similarity (default 0.5).
        epsilon: Near-zero speed threshold (default 0.001).

    Returns:
        MotionScore in [0.0, 100.0], or None if insufficient data.
    """
    if player_motion is None or reference_motion is None:
        return None

    per_landmark_scores: list[float] = []

    p_motions = player_motion.landmark_motions
    r_motions = reference_motion.landmark_motions

    count = min(len(p_motions), len(r_motions))

    for i in range(count):
        p_lm = p_motions[i]
        r_lm = r_motions[i]

        # Skip if either is None
        if p_lm is None or r_lm is None:
            continue

        p_speed = p_lm.speed
        r_speed = r_lm.speed

        # Skip if speed data is unavailable
        if p_speed is None or r_speed is None:
            continue

        # Speed similarity
        if p_speed < epsilon and r_speed < epsilon:
            speed_sim = 1.0
        else:
            max_speed = max(p_speed, r_speed, epsilon)
            speed_sim = 1.0 - abs(p_speed - r_speed) / max_speed

        # Direction similarity
        p_has_dir = (
            p_speed >= epsilon
            and p_lm.direction_x is not None
            and p_lm.direction_y is not None
            and p_lm.direction_z is not None
        )
        r_has_dir = (
            r_speed >= epsilon
            and r_lm.direction_x is not None
            and r_lm.direction_y is not None
            and r_lm.direction_z is not None
        )

        if p_has_dir and r_has_dir:
            # Dot product of unit direction vectors, clamped to [0, 1]
            dot = (
                p_lm.direction_x * r_lm.direction_x  # type: ignore[operator]
                + p_lm.direction_y * r_lm.direction_y  # type: ignore[operator]
                + p_lm.direction_z * r_lm.direction_z  # type: ignore[operator]
            )
            dir_sim = max(0.0, dot)
            per_lm = speed_sim * speed_weight + dir_sim * direction_weight
        else:
            # Direction undefined — use speed similarity only
            per_lm = speed_sim

        per_landmark_scores.append(per_lm)

    if len(per_landmark_scores) == 0:
        return None

    mean_score = sum(per_landmark_scores) / len(per_landmark_scores)
    return mean_score * 100.0
