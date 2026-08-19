"""Joint-angle comparison with circular wraparound handling.

Compares signed angles [-180, 180] using the shortest circular distance.
Handles wraparound correctly: -179° vs +179° → error = 2°.
"""


def compute_angle_score(
    player_angles: dict[str, float | None],
    reference_angles: dict[str, float | None],
    angle_scale: float = 1.0,
) -> float | None:
    """Compare joint angles with correct wraparound.

    Formula:
        For each joint where both player and reference angle are not None:
            abs_diff = abs(player_angle - reference_angle)
            error = min(abs_diff, 360.0 - abs_diff)  # circular shortest distance
        mean_error = sum(errors) / count
        score = max(0.0, 100.0 - mean_error * angle_scale)

    Args:
        player_angles: Dict of joint_name → angle in degrees [-180, 180] or None.
        reference_angles: Dict of joint_name → angle in degrees [-180, 180] or None.
        angle_scale: Converts mean error (degrees) to score deduction.
            Default 1.0 means 100° mean error → score 0.

    Returns:
        AngleScore in [0.0, 100.0], or None if no valid angle pairs exist.
    """
    errors: list[float] = []

    for joint_name, player_angle in player_angles.items():
        if player_angle is None:
            continue
        reference_angle = reference_angles.get(joint_name)
        if reference_angle is None:
            continue

        # Circular angular distance (handles wraparound)
        abs_diff = abs(player_angle - reference_angle)
        error = min(abs_diff, 360.0 - abs_diff)
        errors.append(error)

    if len(errors) == 0:
        return None

    mean_error = sum(errors) / len(errors)
    score = max(0.0, 100.0 - mean_error * angle_scale)
    return score
