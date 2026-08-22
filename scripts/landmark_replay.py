"""Landmark Replay Diagnostic — visual validation of analyzed pose data.

Replays a video with the detected landmarks, skeleton, joint angles, and
motion vectors overlaid. Uses existing ReferenceAnalyzer/ReferenceSequence.

Usage:
    python scripts/landmark_replay.py path/to/video.mp4
    python scripts/landmark_replay.py path/to/video.mp4 --angles
    python scripts/landmark_replay.py path/to/video.mp4 --motion
    python scripts/landmark_replay.py path/to/video.mp4 --normalized
    python scripts/landmark_replay.py path/to/video.mp4 --angles --save out.mp4

Controls:
    q / ESC       — exit
    SPACE         — pause / resume
    Right arrow   — advance 1 frame (while paused)
    Left arrow    — go back 1 frame (while paused)
    1             — playback 1.0x
    2             — playback 2.0x
    5             — playback 0.5x
"""

import argparse
import sys
import time
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from opendance.config.models import (  # noqa: E402
    NormalizationConfig,
    PoseConfig,
    ReferenceConfig,
)
from opendance.motion.landmarks import (  # noqa: E402
    LEFT_ANKLE,
    LEFT_ELBOW,
    LEFT_HIP,
    LEFT_KNEE,
    LEFT_SHOULDER,
    LEFT_WRIST,
    NUM_LANDMARKS,
    RIGHT_ANKLE,
    RIGHT_ELBOW,
    RIGHT_HIP,
    RIGHT_KNEE,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
)
from opendance.motion.motion_result import MotionFeatures  # noqa: E402
from opendance.motion.normalized_pose import NormalizedPose  # noqa: E402
from opendance.ui.skeleton_renderer import POSE_CONNECTIONS  # noqa: E402
from opendance.video.reference_analyzer import ReferenceAnalyzer  # noqa: E402
from opendance.video.reference_sequence import ReferenceSequence  # noqa: E402

# --- Constants ---
MODEL_PATH = str(_project_root / "assets" / "models" / "pose_landmarker.task")
WINDOW_NAME = "Landmark Replay — OpenDance AI"

# Colors (BGR)
COLOR_LANDMARK = (0, 255, 0)
COLOR_LOW_VIS = (0, 165, 255)
COLOR_CONNECTION = (0, 200, 0)
COLOR_NO_POSE = (0, 0, 255)
COLOR_TEXT = (255, 255, 255)
COLOR_PANEL_BG = (40, 40, 40)
COLOR_ANGLE = (255, 200, 0)
COLOR_MOTION = (255, 100, 255)
COLOR_NORM_BG = (30, 30, 30)
COLOR_NORM_LM = (0, 255, 200)

VISIBILITY_THRESHOLD = 0.5

# Joint angle display positions (landmark index for label placement)
ANGLE_LABEL_LANDMARKS = {
    "left_elbow": LEFT_ELBOW,
    "right_elbow": RIGHT_ELBOW,
    "left_shoulder": LEFT_SHOULDER,
    "right_shoulder": RIGHT_SHOULDER,
    "left_hip": LEFT_HIP,
    "right_hip": RIGHT_HIP,
    "left_knee": LEFT_KNEE,
    "right_knee": RIGHT_KNEE,
}

# Key body landmarks for tracking verification
KEY_LANDMARKS = {
    "Head": 0,
    "L.Shoulder": LEFT_SHOULDER,
    "R.Shoulder": RIGHT_SHOULDER,
    "L.Elbow": LEFT_ELBOW,
    "R.Elbow": RIGHT_ELBOW,
    "L.Wrist": LEFT_WRIST,
    "R.Wrist": RIGHT_WRIST,
    "L.Hip": LEFT_HIP,
    "R.Hip": RIGHT_HIP,
    "L.Knee": LEFT_KNEE,
    "R.Knee": RIGHT_KNEE,
    "L.Ankle": LEFT_ANKLE,
    "R.Ankle": RIGHT_ANKLE,
}


def analyze_video(video_path: Path) -> ReferenceSequence:
    """Analyze video using existing ReferenceAnalyzer."""
    pose_cfg = PoseConfig(model_path=MODEL_PATH)
    norm_cfg = NormalizationConfig(enabled=True, visibility_threshold=0.5)
    ref_cfg = ReferenceConfig(cache_directory="", auto_cache=False, sample_fps=30.0)

    analyzer = ReferenceAnalyzer(pose_cfg, norm_cfg, ref_cfg)
    try:
        print("  Analyzing video...")
        sequence = analyzer.analyze(str(video_path))
        print(f"  Done: {len(sequence.poses)} frames analyzed.")
        return sequence
    finally:
        analyzer.close()


def draw_skeleton_from_sequence(
    frame: np.ndarray,
    pose: NormalizedPose,
    video_w: int,
    video_h: int,
) -> None:
    """Draw skeleton on frame using NormalizedPose visibilities and original landmarks.

    Since NormalizedPose stores body-relative coords, we use visibilities
    to determine which landmarks to draw, but reconstruct pixel positions
    from the original video frame dimensions using the pose's body_center/scale.
    """
    # We need original image-space landmarks. Since NormalizedPose stores
    # body-relative, we reverse: pixel = (normalized * scale + center) * image_dim
    # But body_center is already in normalized [0,1] space for image landmarks.
    # Simpler: check which landmarks are valid via visibilities
    # For replay we re-detect per frame — but the task says reuse analyzed data.
    # NormalizedPose.landmarks_2d are body-relative, we need to un-normalize.
    center = pose.body_center
    scale = pose.body_scale

    # Draw connections
    for idx_a, idx_b in POSE_CONNECTIONS:
        if idx_a >= NUM_LANDMARKS or idx_b >= NUM_LANDMARKS:
            continue
        lm_a = pose.landmarks_2d[idx_a]
        lm_b = pose.landmarks_2d[idx_b]
        vis_a = pose.visibilities[idx_a]
        vis_b = pose.visibilities[idx_b]

        if lm_a is None or lm_b is None:
            continue
        if vis_a < VISIBILITY_THRESHOLD or vis_b < VISIBILITY_THRESHOLD:
            continue

        # Un-normalize: pixel = (norm * scale + center) * dim
        ax = int((lm_a[0] * scale + center[0]) * video_w)
        ay = int((lm_a[1] * scale + center[1]) * video_h)
        bx = int((lm_b[0] * scale + center[0]) * video_w)
        by = int((lm_b[1] * scale + center[1]) * video_h)

        cv2.line(frame, (ax, ay), (bx, by), COLOR_CONNECTION, 2)

    # Draw landmarks
    for i in range(NUM_LANDMARKS):
        lm = pose.landmarks_2d[i]
        if lm is None:
            continue

        vis = pose.visibilities[i]
        px = int((lm[0] * scale + center[0]) * video_w)
        py = int((lm[1] * scale + center[1]) * video_h)

        if vis >= VISIBILITY_THRESHOLD:
            cv2.circle(frame, (px, py), 4, COLOR_LANDMARK, -1)
        elif vis >= 0.1:
            cv2.circle(frame, (px, py), 3, COLOR_LOW_VIS, -1)


def draw_angles_overlay(
    frame: np.ndarray,
    pose: NormalizedPose,
    angles: dict[str, float | None],
    video_w: int,
    video_h: int,
) -> None:
    """Draw joint angle values near the corresponding landmark."""
    center = pose.body_center
    scale = pose.body_scale

    for name, angle_val in angles.items():
        if angle_val is None:
            continue
        lm_idx = ANGLE_LABEL_LANDMARKS.get(name)
        if lm_idx is None:
            continue
        lm = pose.landmarks_2d[lm_idx]
        if lm is None:
            continue

        px = int((lm[0] * scale + center[0]) * video_w) + 8
        py = int((lm[1] * scale + center[1]) * video_h) - 5

        text = f"{angle_val:.0f}"
        cv2.putText(frame, text, (px, py),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_ANGLE, 1)


def draw_motion_vectors(
    frame: np.ndarray,
    pose: NormalizedPose,
    motion: MotionFeatures,
    video_w: int,
    video_h: int,
) -> None:
    """Draw small motion vectors at each landmark."""
    center = pose.body_center
    scale = pose.body_scale
    arrow_scale = 0.02  # Scale factor for visual arrow length

    for i, lm_motion in enumerate(motion.landmark_motions):
        if lm_motion is None:
            continue
        if lm_motion.velocity_x is None or lm_motion.velocity_y is None:
            continue

        lm = pose.landmarks_2d[i]
        if lm is None:
            continue
        if pose.visibilities[i] < VISIBILITY_THRESHOLD:
            continue

        px = int((lm[0] * scale + center[0]) * video_w)
        py = int((lm[1] * scale + center[1]) * video_h)

        # Arrow endpoint
        vx = lm_motion.velocity_x * arrow_scale * scale * video_w
        vy = lm_motion.velocity_y * arrow_scale * scale * video_h
        ex = int(px + vx)
        ey = int(py + vy)

        cv2.arrowedLine(frame, (px, py), (ex, ey), COLOR_MOTION, 1,
                        tipLength=0.3)


def draw_normalized_panel(
    pose: NormalizedPose,
    panel_size: int = 300,
) -> np.ndarray:
    """Draw NormalizedPose in a separate viewport (body-relative coords)."""
    panel = np.full((panel_size, panel_size, 3), COLOR_NORM_BG, dtype=np.uint8)

    # Map normalized coords to panel: center at panel center, scale to fit
    cx, cy = panel_size // 2, panel_size // 2
    draw_scale = panel_size * 0.3  # Pixels per normalized unit

    # Draw connections
    for idx_a, idx_b in POSE_CONNECTIONS:
        if idx_a >= NUM_LANDMARKS or idx_b >= NUM_LANDMARKS:
            continue
        lm_a = pose.landmarks_2d[idx_a]
        lm_b = pose.landmarks_2d[idx_b]
        if lm_a is None or lm_b is None:
            continue
        if pose.visibilities[idx_a] < VISIBILITY_THRESHOLD:
            continue
        if pose.visibilities[idx_b] < VISIBILITY_THRESHOLD:
            continue

        ax = int(cx + lm_a[0] * draw_scale)
        ay = int(cy + lm_a[1] * draw_scale)
        bx = int(cx + lm_b[0] * draw_scale)
        by = int(cy + lm_b[1] * draw_scale)
        cv2.line(panel, (ax, ay), (bx, by), (0, 150, 0), 1)

    # Draw landmarks
    for i in range(NUM_LANDMARKS):
        lm = pose.landmarks_2d[i]
        if lm is None:
            continue
        if pose.visibilities[i] < 0.1:
            continue
        px = int(cx + lm[0] * draw_scale)
        py = int(cy + lm[1] * draw_scale)
        color = COLOR_NORM_LM if pose.visibilities[i] >= VISIBILITY_THRESHOLD else COLOR_LOW_VIS
        cv2.circle(panel, (px, py), 3, color, -1)

    cv2.putText(panel, "Normalized", (5, 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLOR_TEXT, 1)
    cv2.putText(panel, f"scale={pose.body_scale:.3f}", (5, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 180, 180), 1)

    return panel


def draw_info_panel(
    frame: np.ndarray,
    frame_idx: int,
    total_frames: int,
    timestamp_ms: int,
    pose: NormalizedPose | None,
    fps: float,
    paused: bool,
    playback_speed: float = 1.0,
) -> None:
    """Draw info overlay on the top of the frame."""
    h, w = frame.shape[:2]
    panel_h = 135

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, panel_h), COLOR_PANEL_BG, -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    # Frame / timestamp
    cv2.putText(frame, f"Frame: {frame_idx + 1}/{total_frames}", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_TEXT, 1)
    cv2.putText(frame, f"Time: {timestamp_ms / 1000:.2f}s", (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_TEXT, 1)

    # Detection status
    if pose is not None and pose.valid:
        status = "DETECTED"
        color = COLOR_LANDMARK
        valid_lm = sum(1 for v in pose.visibilities if v >= VISIBILITY_THRESHOLD)
        cv2.putText(frame, f"Status: {status}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        cv2.putText(frame, f"Landmarks: {valid_lm}/33", (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_TEXT, 1)
        cv2.putText(frame, f"Body scale: {pose.body_scale:.4f}", (10, 98),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_TEXT, 1)
    else:
        cv2.putText(frame, "Status: NO POSE", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_NO_POSE, 2)

    # FPS and playback speed
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 115),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    cv2.putText(frame, f"Playback: {playback_speed:.2f}x", (10, 132),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    # Pause indicator
    if paused:
        cv2.putText(frame, "PAUSED", (w - 80, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 2)


def run_replay(
    video_path: Path,
    sequence: ReferenceSequence,
    show_angles: bool = False,
    show_motion: bool = False,
    show_normalized: bool = False,
    save_path: str | None = None,
) -> None:
    """Main replay loop with real-time playback and aspect-ratio preservation."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print("ERROR: Cannot open video.", file=sys.stderr)
        return

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    video_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    aspect_ratio = video_w / video_h

    total_analysis_frames = len(sequence.poses)
    sample_interval_ms = 1000.0 / sequence.metadata.fps
    frame_interval_s = 1.0 / source_fps

    print(f"  Resolution: {video_w}x{video_h}")
    print(f"  Aspect ratio: {aspect_ratio:.4f} ({video_w}:{video_h})")
    print(f"  Source FPS: {source_fps:.2f}")
    print(f"  Frame interval: {frame_interval_s * 1000:.2f} ms")

    # Video writer (saves at native resolution, no aspect change)
    writer = None
    if save_path:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
        out_w = video_w + (300 if show_normalized else 0)
        writer = cv2.VideoWriter(
            save_path, fourcc, source_fps, (out_w, video_h),
        )
        print(f"  Saving to: {save_path}")

    # Create window preserving aspect ratio
    try:
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_KEEPRATIO)
        # Set initial window size respecting aspect ratio
        max_display_h = 800
        display_h = min(video_h, max_display_h)
        display_w = int(display_h * aspect_ratio)
        if show_normalized:
            norm_w = int(300 * display_h / video_h)
            display_w += norm_w
        cv2.resizeWindow(WINDOW_NAME, display_w, display_h)
    except cv2.error as exc:
        print(f"ERROR: No GUI backend: {exc}", file=sys.stderr)
        cap.release()
        return

    # Pre-read all frames for seeking support
    all_frames: list[np.ndarray | None] = []
    print("  Loading video frames...")
    while True:
        ret, frm = cap.read()
        if not ret or frm is None:
            break
        all_frames.append(frm)
    cap.release()
    print(f"  Loaded {len(all_frames)} frames.")

    total_frames_available = min(len(all_frames), total_analysis_frames)

    paused = False
    frame_idx = 0
    playback_speed = 1.0
    frame_timestamps: list[float] = []
    next_frame_time = time.perf_counter()

    try:
        while 0 <= frame_idx < total_frames_available:
            frame = all_frames[frame_idx]
            if frame is None:
                frame_idx += 1
                continue

            # Render onto native-resolution copy (no resize of content)
            display = frame.copy()
            now = time.perf_counter()
            frame_timestamps.append(now)
            if len(frame_timestamps) > 60:
                frame_timestamps = frame_timestamps[-60:]

            # Actual display FPS
            fps = 0.0
            if len(frame_timestamps) >= 2:
                elapsed = frame_timestamps[-1] - frame_timestamps[0]
                if elapsed > 0:
                    fps = (len(frame_timestamps) - 1) / elapsed

            # Get analysis data for this frame
            pose = sequence.poses[frame_idx]
            angles = (
                sequence.joint_angles[frame_idx]
                if frame_idx < len(sequence.joint_angles) else None
            )
            motion = (
                sequence.motion_features[frame_idx]
                if frame_idx < len(sequence.motion_features) else None
            )

            timestamp_ms = int(frame_idx * sample_interval_ms)

            # Draw skeleton on native-resolution frame
            if pose is not None and pose.valid:
                draw_skeleton_from_sequence(display, pose, video_w, video_h)

                if show_angles and angles is not None:
                    draw_angles_overlay(
                        display, pose, angles, video_w, video_h,
                    )

                if show_motion and motion is not None:
                    draw_motion_vectors(
                        display, pose, motion, video_w, video_h,
                    )

            # Info panel
            draw_info_panel(
                display, frame_idx, total_frames_available,
                timestamp_ms, pose, fps, paused, playback_speed,
            )

            # Normalized panel (appended at native height)
            if show_normalized and pose is not None and pose.valid:
                norm_panel = draw_normalized_panel(pose)
                norm_resized = cv2.resize(norm_panel, (300, video_h))
                display = np.hstack([display, norm_resized])
            elif show_normalized:
                blank = np.full(
                    (video_h, 300, 3), COLOR_NORM_BG, dtype=np.uint8,
                )
                cv2.putText(
                    blank, "NO POSE", (100, video_h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_NO_POSE, 2,
                )
                display = np.hstack([display, blank])

            # Save at native resolution
            if writer is not None:
                writer.write(display)

            # Show (WINDOW_KEEPRATIO handles display scaling)
            cv2.imshow(WINDOW_NAME, display)

            # --- Timing-based playback ---
            if paused:
                wait_ms = 0  # Block until key
            else:
                # Compute how long to wait for real-time playback
                next_frame_time += frame_interval_s / playback_speed
                remaining = next_frame_time - time.perf_counter()
                wait_ms = max(1, int(remaining * 1000))

            key = cv2.waitKey(wait_ms) & 0xFF

            # Handle keys
            if key == ord("q") or key == 27:  # q / ESC
                break
            elif key == ord(" "):  # SPACE
                paused = not paused
                if not paused:
                    # Reset timing on unpause
                    next_frame_time = time.perf_counter()
            elif key == ord("1"):
                playback_speed = 1.0
            elif key == ord("2"):
                playback_speed = 2.0
            elif key == ord("5"):
                playback_speed = 0.5
            elif paused:
                # Arrow keys on Windows: waitKey returns special codes
                # Right arrow = 2555904 & 0xFF = 0 (or 83 on Linux)
                # Left arrow = 2424832 & 0xFF = 0 (or 81 on Linux)
                # Use waitKeyEx for proper detection on Windows
                if key == 0:
                    # Re-read with waitKeyEx for arrow detection
                    pass

            # Arrow key handling (works across platforms)
            if paused and key in (83, 0):
                # Attempt right arrow: try platform-specific codes
                frame_idx += 1
                continue
            if paused and key == 81:
                frame_idx = max(0, frame_idx - 1)
                continue

            # Window closed check
            try:
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break
            except cv2.error:
                break

            if not paused:
                frame_idx += 1

    except KeyboardInterrupt:
        print("  Interrupted.")
    finally:
        if writer is not None:
            writer.release()
            print(f"  Video saved: {save_path}")
        cv2.destroyAllWindows()

    # Summary
    print()
    print("=" * 50)
    print("  REPLAY SUMMARY")
    print("=" * 50)
    detected = sum(1 for p in sequence.poses if p is not None and p.valid)
    no_pose = total_analysis_frames - detected
    rate = (
        (detected / total_analysis_frames * 100)
        if total_analysis_frames > 0 else 0
    )
    scales = [
        p.body_scale for p in sequence.poses if p is not None and p.valid
    ]

    print(f"  Total frames:    {total_analysis_frames}")
    print(f"  Detected:        {detected}")
    print(f"  No pose:         {no_pose}")
    print(f"  Detection rate:  {rate:.1f}%")
    if scales:
        print(f"  Body scale min:  {min(scales):.4f}")
        print(f"  Body scale max:  {max(scales):.4f}")
        print(f"  Body scale mean: {np.mean(scales):.4f}")
    print("=" * 50)


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Landmark Replay — OpenDance AI diagnostic",
    )
    parser.add_argument("video_path", help="Path to video file")
    parser.add_argument("--angles", action="store_true",
                        help="Show joint angles at landmarks")
    parser.add_argument("--motion", action="store_true",
                        help="Show motion vectors")
    parser.add_argument("--normalized", action="store_true",
                        help="Show normalized pose panel")
    parser.add_argument("--save", metavar="PATH",
                        help="Save replay as MP4")

    args = parser.parse_args()

    video_path = Path(args.video_path)
    if not video_path.exists():
        print(f"ERROR: Video not found: {args.video_path}", file=sys.stderr)
        return 1
    if not Path(MODEL_PATH).exists():
        print("ERROR: Model not found. Run: python scripts/download_models.py",
              file=sys.stderr)
        return 1

    print("=" * 50)
    print("  LANDMARK REPLAY — OpenDance AI")
    print("=" * 50)
    print(f"  Video: {video_path.name}")
    print(f"  Angles: {'ON' if args.angles else 'OFF'}")
    print(f"  Motion: {'ON' if args.motion else 'OFF'}")
    print(f"  Normalized: {'ON' if args.normalized else 'OFF'}")
    print(f"  Save: {args.save or 'OFF'}")
    print()

    sequence = analyze_video(video_path)

    print()
    print("  Controls: SPACE=pause, q/ESC=quit, arrows=step")
    print()

    run_replay(
        video_path,
        sequence,
        show_angles=args.angles,
        show_motion=args.motion,
        show_normalized=args.normalized,
        save_path=args.save,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
