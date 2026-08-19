"""Camera Pose Detection Diagnostic Tool.

Opens the local webcam and displays real-time pose detection using the existing
OpenDance AI PoseDetector. This is a standalone diagnostic/validation utility,
NOT production application code.

Usage:
    python scripts/camera_diagnostic.py

Controls:
    q / ESC — exit cleanly

Requirements:
    - A local webcam accessible at device index 0
    - The MediaPipe pose model at assets/models/pose_landmarker.task
      (run `python scripts/download_models.py` first)
"""

import sys
import time
from pathlib import Path

# Ensure src/ is importable when running as a script
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from opendance.config.models import NormalizationConfig, PoseConfig  # noqa: E402
from opendance.motion.normalizer import normalize_pose  # noqa: E402
from opendance.pose.detector import PoseDetector  # noqa: E402
from opendance.pose.result import PoseResult  # noqa: E402
from opendance.ui.skeleton_renderer import render_skeleton  # noqa: E402

# --- Configuration ---

WINDOW_NAME = "OpenDance AI - Camera Diagnostic"
DEVICE_INDEX = 0
VISIBILITY_THRESHOLD = 0.5

# Colors (BGR)
COLOR_DETECTED = (0, 255, 0)       # Green
COLOR_NO_POSE = (0, 0, 255)        # Red
COLOR_TEXT_BG = (40, 40, 40)       # Dark gray
COLOR_TEXT = (255, 255, 255)       # White
COLOR_FPS = (0, 255, 255)         # Yellow
COLOR_LOW_VIS = (0, 165, 255)     # Orange — low visibility landmarks


def compute_fps(timestamps: list[float], window: int = 30) -> float:
    """Compute FPS from recent frame timestamps using a rolling window."""
    if len(timestamps) < 2:
        return 0.0
    recent = timestamps[-window:]
    if len(recent) < 2:
        return 0.0
    elapsed = recent[-1] - recent[0]
    if elapsed <= 0:
        return 0.0
    return (len(recent) - 1) / elapsed


def count_visible_landmarks(pose_result: PoseResult, threshold: float) -> int:
    """Count landmarks meeting the visibility threshold."""
    return sum(1 for lm in pose_result.landmarks if lm.visibility >= threshold)


def draw_info_overlay(
    frame: np.ndarray,
    fps: float,
    pose_result: PoseResult,
    body_scale: float | None,
    visible_count: int,
) -> np.ndarray:
    """Draw diagnostic information overlay on the frame."""
    h, w = frame.shape[:2]

    # Background panel for readability
    panel_h = 140
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, panel_h), COLOR_TEXT_BG, -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    # FPS
    fps_text = f"FPS: {fps:.1f}"
    cv2.putText(frame, fps_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_FPS, 2)

    # Detection status
    if pose_result.is_empty:
        status_text = "NO POSE"
        status_color = COLOR_NO_POSE
    else:
        status_text = "DETECTED"
        status_color = COLOR_DETECTED

    cv2.putText(
        frame, f"Status: {status_text}", (10, 55),
        cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2,
    )

    # Landmark count
    if not pose_result.is_empty:
        total = len(pose_result.landmarks)
        lm_text = f"Landmarks: {visible_count}/{total}"
        cv2.putText(
            frame, lm_text, (10, 85),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_TEXT, 1,
        )

    # Body scale
    if body_scale is not None:
        scale_text = f"Body scale: {body_scale:.4f}"
        cv2.putText(
            frame, scale_text, (10, 110),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_TEXT, 1,
        )

    # Timestamp
    ts_text = f"Frame ts: {pose_result.timestamp_ms} ms"
    cv2.putText(
        frame, ts_text, (10, 135),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1,
    )

    return frame


def draw_low_visibility_landmarks(
    frame: np.ndarray,
    pose_result: PoseResult,
    vis_threshold: float,
    min_visibility: float = 0.1,
) -> np.ndarray:
    """Draw low-visibility landmarks in a different color to distinguish them."""
    if pose_result.is_empty:
        return frame

    h, w = frame.shape[:2]
    for lm in pose_result.landmarks:
        if min_visibility <= lm.visibility < vis_threshold:
            pt = (int(lm.x * w), int(lm.y * h))
            cv2.circle(frame, pt, 3, COLOR_LOW_VIS, -1)

    return frame


def run_diagnostic() -> int:
    """Main diagnostic loop. Returns exit code (0=success, 1=error)."""
    # Initialize webcam
    print(f"Opening webcam (device {DEVICE_INDEX})...")
    cap = cv2.VideoCapture(DEVICE_INDEX)

    if not cap.isOpened():
        print("ERROR: Cannot open webcam. Check that a camera is connected.", file=sys.stderr)
        return 1

    # Initialize pose detector
    model_path = _project_root / "assets" / "models" / "pose_landmarker.task"
    if not model_path.exists():
        print(
            f"ERROR: Pose model not found at {model_path}\n"
            "Run: python scripts/download_models.py",
            file=sys.stderr,
        )
        cap.release()
        return 1

    print("Initializing PoseDetector...")
    try:
        pose_config = PoseConfig(
            model_path=str(model_path),
            skeleton_visibility_threshold=VISIBILITY_THRESHOLD,
        )
        detector = PoseDetector(pose_config)
    except Exception as exc:
        print(f"ERROR: Failed to initialize PoseDetector: {exc}", file=sys.stderr)
        cap.release()
        return 1

    norm_config = NormalizationConfig(
        enabled=True,
        visibility_threshold=VISIBILITY_THRESHOLD,
    )

    # Check if display is available
    try:
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    except cv2.error as exc:
        print(f"ERROR: Cannot create display window (no GUI backend): {exc}", file=sys.stderr)
        detector.close()
        cap.release()
        return 1

    print("Camera diagnostic running. Press 'q' or ESC to exit.")
    print(f"Window: {WINDOW_NAME}")

    timestamps: list[float] = []
    frame_count = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("WARNING: Failed to read frame, retrying...", file=sys.stderr)
                time.sleep(0.01)
                continue

            frame_count += 1
            now = time.time()
            timestamps.append(now)

            # Keep only last 60 timestamps for FPS calculation
            if len(timestamps) > 60:
                timestamps = timestamps[-60:]

            # Compute timestamp_ms (monotonically increasing)
            timestamp_ms = int(now * 1000)

            # Run pose detection using existing PoseDetector
            pose_result = detector.detect(frame, timestamp_ms=timestamp_ms)

            # Compute body scale via normalization if pose available
            body_scale: float | None = None
            if not pose_result.is_empty:
                norm_result = normalize_pose(pose_result, norm_config)
                if norm_result.valid:
                    body_scale = norm_result.body_scale

            # Draw skeleton using existing renderer
            render_skeleton(
                frame,
                pose_result,
                visibility_threshold=VISIBILITY_THRESHOLD,
                landmark_color=COLOR_DETECTED,
            )

            # Draw low-visibility landmarks in orange
            draw_low_visibility_landmarks(frame, pose_result, VISIBILITY_THRESHOLD)

            # Draw info overlay
            fps = compute_fps(timestamps)
            visible_count = count_visible_landmarks(pose_result, VISIBILITY_THRESHOLD)
            draw_info_overlay(frame, fps, pose_result, body_scale, visible_count)

            # Display
            cv2.imshow(WINDOW_NAME, frame)

            # Check for exit key
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:  # q or ESC
                print("Exit requested by user.")
                break

            # Also check if window was closed
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                print("Window closed by user.")
                break

    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C).")
    except Exception as exc:
        print(f"ERROR: Unexpected error during diagnostic: {exc}", file=sys.stderr)
    finally:
        # Clean up all resources
        print("Releasing resources...")
        detector.close()
        cap.release()
        cv2.destroyAllWindows()
        print(f"Done. Processed {frame_count} frames.")

    return 0


if __name__ == "__main__":
    sys.exit(run_diagnostic())
