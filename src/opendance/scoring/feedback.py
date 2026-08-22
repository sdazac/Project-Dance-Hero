"""Feedback generation: structured FeedbackItems from comparison data.

Produces deterministic, machine-readable feedback identifying body regions
with significant angular or positional errors. UI-independent.
"""

import math

from opendance.motion.landmarks import JOINT_ANGLES
from opendance.motion.normalized_pose import NormalizedPose
from opendance.scoring.models import LANDMARK_REGIONS, FeedbackItem


def generate_feedback(
    player_pose: NormalizedPose,
    reference_pose: NormalizedPose,
    player_angles: dict[str, float | None],
    reference_angles: dict[str, float | None],
    significance_threshold: float = 0.1,
) -> list[FeedbackItem]:
    """Generate structured feedback for errors above significance threshold.

    Produces feedback in deterministic order:
    1. Joint-angle feedback in JOINT_ANGLES definition order.
    2. Landmark-position feedback in ascending landmark index order.

    Angle feedback:
        error = min(abs(player - reference), 360 - abs(player - reference))
        severity = min(1.0, error / 90.0)
        Emit if severity > significance_threshold.

    Pose-position feedback:
        distance = sqrt((px - rx)² + (py - ry)²)  [2D x,y only]
        severity = min(1.0, distance / 0.5)
        Emit if distance > significance_threshold.

    Missing angles or landmarks are silently skipped (no feedback generated).

    Args:
        player_pose: Player's NormalizedPose.
        reference_pose: Reference NormalizedPose at aligned frame.
        player_angles: Player's joint angles dict.
        reference_angles: Reference's joint angles dict.
        significance_threshold: Minimum severity/error to emit feedback.

    Returns:
        Deterministically-ordered list of FeedbackItem objects.
    """
    items: list[FeedbackItem] = []

    # 1. Angle feedback — in JOINT_ANGLES definition order
    for joint_name in JOINT_ANGLES:
        p_angle = player_angles.get(joint_name)
        r_angle = reference_angles.get(joint_name)

        if p_angle is None or r_angle is None:
            continue

        abs_diff = abs(p_angle - r_angle)
        error = min(abs_diff, 360.0 - abs_diff)
        severity = min(1.0, error / 90.0)

        if error > significance_threshold * 180.0:
            items.append(FeedbackItem(
                body_region=joint_name,
                issue_type="angle_mismatch",
                severity=severity,
                description=f"{joint_name} angle differs by {error:.0f}\u00b0",
            ))

    # 2. Position feedback — ascending landmark index order
    p_lm = player_pose.landmarks_2d
    r_lm = reference_pose.landmarks_2d
    count = min(len(p_lm), len(r_lm))

    for i in range(count):
        p = p_lm[i]
        r = r_lm[i]

        if p is None or r is None:
            continue

        dx = p[0] - r[0]
        dy = p[1] - r[1]
        distance = math.sqrt(dx * dx + dy * dy)
        severity = min(1.0, distance / 0.5)

        if distance > significance_threshold:
            region = LANDMARK_REGIONS.get(i, "unknown")
            items.append(FeedbackItem(
                body_region=region,
                issue_type="position_off",
                severity=severity,
                description=(
                    f"{region} (landmark {i}) position off by "
                    f"{distance:.3f} body-units"
                ),
            ))

    return items
