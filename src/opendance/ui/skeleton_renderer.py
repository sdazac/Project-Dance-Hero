"""Skeleton overlay rendering for OpenDance AI.

Draws pose landmarks and bone connections onto a camera frame.
Pure function — no class state needed.
"""

import cv2
import numpy as np

from opendance.pose.result import PoseResult

# MediaPipe Pose bone connections (pairs of landmark indices)
POSE_CONNECTIONS: list[tuple[int, int]] = [
    (0, 1), (1, 2), (2, 3), (3, 7),      # left eye chain
    (0, 4), (4, 5), (5, 6), (6, 8),      # right eye chain
    (9, 10),                               # mouth
    (11, 12),                              # shoulders
    (11, 13), (13, 15),                    # left arm
    (12, 14), (14, 16),                    # right arm
    (11, 23), (12, 24), (23, 24),          # torso
    (23, 25), (25, 27),                    # left leg
    (24, 26), (26, 28),                    # right leg
    (27, 29), (29, 31), (31, 27),          # left foot
    (28, 30), (30, 32), (32, 28),          # right foot
    (15, 17), (15, 19), (15, 21),          # left hand
    (16, 18), (16, 20), (16, 22),          # right hand
]


def render_skeleton(
    frame: np.ndarray,
    pose_result: PoseResult,
    visibility_threshold: float = 0.5,
    landmark_color: tuple[int, int, int] = (0, 255, 0),
    connection_color: tuple[int, int, int] = (0, 200, 0),
    landmark_radius: int = 4,
    connection_thickness: int = 2,
) -> np.ndarray:
    """Draw skeleton overlay on frame. Returns the annotated frame.

    If pose_result is empty, returns the frame unmodified.
    Only draws landmarks with visibility >= visibility_threshold.
    Bone connections drawn only when both endpoints meet the threshold.

    Args:
        frame: BGR image (modified in-place for performance).
        pose_result: Pose detection result with landmarks.
        visibility_threshold: Minimum visibility to draw a landmark.
        landmark_color: BGR color for landmark circles.
        connection_color: BGR color for bone connection lines.
        landmark_radius: Radius of landmark circles in pixels.
        connection_thickness: Thickness of bone connection lines in pixels.

    Returns:
        The annotated frame (same object as input, modified in-place).
    """
    if pose_result.is_empty:
        return frame

    h, w = frame.shape[:2]
    landmarks = pose_result.landmarks

    # Draw bone connections first (under landmarks)
    for idx_a, idx_b in POSE_CONNECTIONS:
        if idx_a >= len(landmarks) or idx_b >= len(landmarks):
            continue
        lm_a = landmarks[idx_a]
        lm_b = landmarks[idx_b]
        if lm_a.visibility >= visibility_threshold and lm_b.visibility >= visibility_threshold:
            pt_a = (int(lm_a.x * w), int(lm_a.y * h))
            pt_b = (int(lm_b.x * w), int(lm_b.y * h))
            cv2.line(frame, pt_a, pt_b, connection_color, connection_thickness)

    # Draw landmark points on top
    for lm in landmarks:
        if lm.visibility >= visibility_threshold:
            pt = (int(lm.x * w), int(lm.y * h))
            cv2.circle(frame, pt, landmark_radius, landmark_color, -1)

    return frame
