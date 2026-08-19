"""Pose comparison: 2D (x, y) Euclidean distance between normalized landmarks.

Compares body-normalized image-space landmarks using only x and y coordinates.
The z-component is NOT included in Phase 3 pose scoring.
"""

import math

from opendance.motion.normalized_pose import NormalizedPose


def compute_pose_score(
    player_pose: NormalizedPose,
    reference_pose: NormalizedPose,
    pose_scale_factor: float = 200.0,
    min_valid_landmarks: int = 8,
) -> float | None:
    """Compare normalized 2D landmark positions (x, y only).

    Formula:
        For each landmark i where both player[i] and reference[i] are not None:
            dist_i = sqrt((px - rx)² + (py - ry)²)
        mean_distance = sum(dist_i) / count
        score = max(0.0, 100.0 - mean_distance * pose_scale_factor)

    Args:
        player_pose: Player's NormalizedPose for the current frame.
        reference_pose: Reference NormalizedPose at the aligned frame.
        pose_scale_factor: Converts mean distance to score deduction.
            Default 200.0 means 0.5 body-units → score 0.
        min_valid_landmarks: Minimum number of valid landmark pairs required.
            Returns None if fewer pairs are available.

    Returns:
        PoseScore in [0.0, 100.0], or None if insufficient valid landmarks.
    """
    player_lm = player_pose.landmarks_2d
    reference_lm = reference_pose.landmarks_2d

    # Compute distances for valid pairs (x, y only — z excluded)
    distances: list[float] = []
    count = min(len(player_lm), len(reference_lm))

    for i in range(count):
        p = player_lm[i]
        r = reference_lm[i]
        if p is not None and r is not None:
            dx = p[0] - r[0]
            dy = p[1] - r[1]
            dist = math.sqrt(dx * dx + dy * dy)
            distances.append(dist)

    if len(distances) < min_valid_landmarks:
        return None

    mean_distance = sum(distances) / len(distances)
    score = max(0.0, 100.0 - mean_distance * pose_scale_factor)
    return score
