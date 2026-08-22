"""Joint angle calculation using signed 2D angles (atan2).

Computes signed angles at defined joints from NormalizedPose landmarks_2d.
Output range: [-180, 180] degrees.
Formula: angle = atan2(cross, dot) where cross = BA_x*BC_y - BA_y*BC_x.
"""

import math

from opendance.motion.landmarks import JOINT_ANGLES
from opendance.motion.normalized_pose import NormalizedPose


def compute_joint_angles(
    normalized_pose: NormalizedPose,
) -> dict[str, float | None]:
    """Compute signed 2D joint angles from NormalizedPose.landmarks_2d.

    For each joint defined in JOINT_ANGLES (proximal, joint_center, distal):
      BA = proximal - joint_center
      BC = distal - joint_center
      cross = BA_x * BC_y - BA_y * BC_x
      dot = BA_x * BC_x + BA_y * BC_y
      angle = atan2(cross, dot) * 180 / pi

    Returns:
        dict mapping joint name → signed angle in degrees [-180, 180],
        or None if any required landmark is None or vectors are degenerate
        (zero-length).
    """
    results: dict[str, float | None] = {}
    landmarks = normalized_pose.landmarks_2d

    for joint_name, (prox_idx, joint_idx, dist_idx) in JOINT_ANGLES.items():
        # Check all indices are valid
        if (
            prox_idx >= len(landmarks)
            or joint_idx >= len(landmarks)
            or dist_idx >= len(landmarks)
        ):
            results[joint_name] = None
            continue

        prox = landmarks[prox_idx]
        joint = landmarks[joint_idx]
        dist = landmarks[dist_idx]

        # Any missing landmark → None
        if prox is None or joint is None or dist is None:
            results[joint_name] = None
            continue

        # Compute vectors BA and BC (2D: use x, y only)
        ba_x = prox[0] - joint[0]
        ba_y = prox[1] - joint[1]
        bc_x = dist[0] - joint[0]
        bc_y = dist[1] - joint[1]

        # Check for degenerate (zero-length) vectors
        ba_len_sq = ba_x * ba_x + ba_y * ba_y
        bc_len_sq = bc_x * bc_x + bc_y * bc_y

        if ba_len_sq < 1e-12 or bc_len_sq < 1e-12:
            results[joint_name] = None
            continue

        # Signed angle via atan2(cross, dot)
        cross = ba_x * bc_y - ba_y * bc_x
        dot = ba_x * bc_x + ba_y * bc_y
        angle_rad = math.atan2(cross, dot)
        angle_deg = math.degrees(angle_rad)

        results[joint_name] = angle_deg

    return results
