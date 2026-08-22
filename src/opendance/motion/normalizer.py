"""Pose normalization: transforms PoseResult into body-relative NormalizedPose.

Pure single-frame function. No temporal state or interpolation.
Prefers world landmarks for body center/scale when sufficient visibility.
Falls back to image-space landmarks when world data is unavailable.

Body-normalized units:
    All coordinates are translated so body_center = (0,0,0) then divided by
    body_scale (Euclidean distance between left_shoulder and right_hip in the
    chosen coordinate space). The result is dimensionless: one unit equals
    the shoulder-to-hip distance regardless of whether the source was metric
    world-space or pixel-normalized image-space.
"""

import math

from opendance.config.models import NormalizationConfig
from opendance.motion.landmarks import (
    BODY_CENTER_LANDMARKS,
    BODY_SCALE_LANDMARKS,
    NUM_LANDMARKS,
)
from opendance.motion.normalized_pose import NormalizedPose
from opendance.pose.result import PoseResult


def _landmark_visible(
    visibility: float, threshold: float
) -> bool:
    """Check if a landmark meets the visibility threshold."""
    return visibility >= threshold


def _euclidean_distance(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> float:
    """Euclidean distance between two 3D points."""
    return math.sqrt(
        (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
    )


def _midpoint(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Midpoint of two 3D points."""
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, (a[2] + b[2]) / 2.0)


def normalize_pose(
    pose_result: PoseResult,
    config: NormalizationConfig,
) -> NormalizedPose:
    """Transform PoseResult into body-relative NormalizedPose.

    Algorithm:
    1. Select coordinate space: prefer world_landmarks if body center/scale
       landmarks have sufficient visibility; else fall back to image landmarks.
    2. Compute body_center = midpoint(left_hip, right_hip).
       - Both hips unreliable → return invalid.
       - One hip unreliable → use available hip as approximate center.
    3. Compute body_scale = distance(left_shoulder, right_hip).
       - Either unreliable → return invalid.
       - Scale < min_body_scale → return invalid.
    4. For each landmark: if visible → (coord - center) / scale; else → None.
    5. Process world landmarks into landmarks_3d (None if unavailable).
    6. Preserve original visibility and presence values.

    This function:
    - Does NOT modify the input PoseResult.
    - Does NOT perform temporal interpolation.
    - Is deterministic and thread-safe.
    """
    if pose_result.is_empty:
        return NormalizedPose.invalid(timestamp_ms=pose_result.timestamp_ms)

    threshold = config.visibility_threshold
    min_scale = config.min_body_scale

    # Extract visibility/presence from input
    visibilities = tuple(lm.visibility for lm in pose_result.landmarks)
    presences = tuple(lm.presence for lm in pose_result.landmarks)

    # Determine if world landmarks are usable for center/scale
    hip_l_idx, hip_r_idx = BODY_CENTER_LANDMARKS
    shoulder_l_idx, hip_r_scale_idx = BODY_SCALE_LANDMARKS

    world_available = (
        len(pose_result.world_landmarks) == NUM_LANDMARKS
        and _landmark_visible(pose_result.world_landmarks[hip_l_idx].visibility, threshold)
        and _landmark_visible(pose_result.world_landmarks[hip_r_idx].visibility, threshold)
        and _landmark_visible(
            pose_result.world_landmarks[shoulder_l_idx].visibility, threshold
        )
        and _landmark_visible(
            pose_result.world_landmarks[hip_r_scale_idx].visibility, threshold
        )
    )

    # Select coordinate source for center/scale computation
    if world_available:
        source = pose_result.world_landmarks
    else:
        source = pose_result.landmarks  # type: ignore[assignment]

    # Compute body center
    hip_l_vis = source[hip_l_idx].visibility
    hip_r_vis = source[hip_r_idx].visibility
    hip_l_reliable = _landmark_visible(hip_l_vis, threshold)
    hip_r_reliable = _landmark_visible(hip_r_vis, threshold)

    if not hip_l_reliable and not hip_r_reliable:
        return NormalizedPose.invalid(timestamp_ms=pose_result.timestamp_ms)

    if hip_l_reliable and hip_r_reliable:
        hip_l_coord = (source[hip_l_idx].x, source[hip_l_idx].y, source[hip_l_idx].z)
        hip_r_coord = (source[hip_r_idx].x, source[hip_r_idx].y, source[hip_r_idx].z)
        body_center = _midpoint(hip_l_coord, hip_r_coord)
    elif hip_l_reliable:
        body_center = (source[hip_l_idx].x, source[hip_l_idx].y, source[hip_l_idx].z)
    else:
        body_center = (source[hip_r_idx].x, source[hip_r_idx].y, source[hip_r_idx].z)

    # Compute body scale
    shoulder_vis = source[shoulder_l_idx].visibility
    hip_scale_vis = source[hip_r_scale_idx].visibility

    if not _landmark_visible(shoulder_vis, threshold) or not _landmark_visible(
        hip_scale_vis, threshold
    ):
        return NormalizedPose.invalid(timestamp_ms=pose_result.timestamp_ms)

    shoulder_coord = (
        source[shoulder_l_idx].x,
        source[shoulder_l_idx].y,
        source[shoulder_l_idx].z,
    )
    hip_scale_coord = (
        source[hip_r_scale_idx].x,
        source[hip_r_scale_idx].y,
        source[hip_r_scale_idx].z,
    )
    body_scale = _euclidean_distance(shoulder_coord, hip_scale_coord)

    if body_scale < min_scale:
        return NormalizedPose.invalid(timestamp_ms=pose_result.timestamp_ms)

    # Normalize image-space landmarks (2D)
    landmarks_2d: list[tuple[float, float, float] | None] = []
    for i in range(NUM_LANDMARKS):
        lm = pose_result.landmarks[i]
        if _landmark_visible(lm.visibility, threshold):
            nx = (lm.x - body_center[0]) / body_scale
            ny = (lm.y - body_center[1]) / body_scale
            nz = (lm.z - body_center[2]) / body_scale
            landmarks_2d.append((nx, ny, nz))
        else:
            landmarks_2d.append(None)

    # Normalize world landmarks (3D) if available
    landmarks_3d: tuple[tuple[float, float, float] | None, ...] | None = None
    if len(pose_result.world_landmarks) == NUM_LANDMARKS:
        lm3d_list: list[tuple[float, float, float] | None] = []
        for i in range(NUM_LANDMARKS):
            wl = pose_result.world_landmarks[i]
            if _landmark_visible(wl.visibility, threshold):
                nx = (wl.x - body_center[0]) / body_scale
                ny = (wl.y - body_center[1]) / body_scale
                nz = (wl.z - body_center[2]) / body_scale
                lm3d_list.append((nx, ny, nz))
            else:
                lm3d_list.append(None)
        landmarks_3d = tuple(lm3d_list)

    return NormalizedPose(
        timestamp_ms=pose_result.timestamp_ms,
        landmarks_2d=tuple(landmarks_2d),
        landmarks_3d=landmarks_3d,
        visibilities=visibilities,
        presences=presences,
        body_center=body_center,
        body_scale=body_scale,
        valid=True,
    )
