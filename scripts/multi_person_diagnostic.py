"""Multi-Person Detection Diagnostic — OpenDance AI.

Processes a video and reports multi-person detection statistics.
Uses MultiPoseDetector to detect all candidates and select primary.

Usage:
    python scripts/multi_person_diagnostic.py path/to/video.mp4
    python scripts/multi_person_diagnostic.py path/to/video.mp4 --preview
    python scripts/multi_person_diagnostic.py path/to/video.mp4 --max-poses 3

Controls (--preview mode):
    q / ESC — exit
"""

import argparse
import sys
from pathlib import Path

# Ensure stdout handles unicode when redirected on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from opendance.config.models import PoseConfig  # noqa: E402
from opendance.pose.multi_detector import (  # noqa: E402
    MultiPoseDetector,
    PoseCandidate,
    TrackState,
)

MODEL_PATH = str(
    _project_root / "assets" / "models" / "pose_landmarker.task"
)

# Colors (BGR)
COLOR_PRIMARY = (0, 255, 0)
COLOR_SECONDARY = (255, 165, 0)
COLOR_TEXT = (255, 255, 255)
COLOR_PANEL_BG = (40, 40, 40)

WINDOW_NAME = "Multi-Person Diagnostic — OpenDance AI"


def draw_candidate_skeleton(
    frame: np.ndarray,
    candidate: PoseCandidate,
    color: tuple[int, int, int],
    label: str,
    vis_threshold: float = 0.5,
) -> None:
    """Draw landmarks for a candidate on frame."""
    h, w = frame.shape[:2]
    landmarks = candidate.pose_result.landmarks

    for lm in landmarks:
        if lm.visibility >= vis_threshold:
            px = int(lm.x * w)
            py = int(lm.y * h)
            cv2.circle(frame, (px, py), 3, color, -1)

    # Draw label near center
    cx = int(candidate.center_x * w)
    cy = int(candidate.center_y * h) - 20
    cv2.putText(
        frame, label, (cx - 30, cy),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2,
    )
    area_text = f"area={candidate.body_area:.4f}"
    cv2.putText(
        frame, area_text, (cx - 30, cy + 18),
        cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1,
    )


def run_diagnostic(
    video_path: Path,
    max_poses: int = 5,
    preview: bool = False,
) -> int:
    """Run multi-person diagnostic on video."""
    if not Path(MODEL_PATH).exists():
        print(
            "ERROR: Model not found. "
            "Run: python scripts/download_models.py",
            file=sys.stderr,
        )
        return 1

    config = PoseConfig(
        model_path=MODEL_PATH,
        skeleton_visibility_threshold=0.5,
        max_poses=max_poses,
    )
    detector = MultiPoseDetector(config)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"ERROR: Cannot open video: {video_path}", file=sys.stderr)
        return 1

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_interval_ms = 1000.0 / source_fps

    print("=" * 60)
    print("  MULTI-PERSON DIAGNOSTIC — OpenDance AI")
    print("=" * 60)
    print(f"  Video: {video_path.name}")
    print(f"  Frames: {total_frames}")
    print(f"  FPS: {source_fps:.2f}")
    print(f"  Max poses: {max_poses}")
    print(f"  Preview: {'ON' if preview else 'OFF'}")
    print()

    if preview:
        try:
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        except cv2.error as exc:
            print(
                f"ERROR: Cannot create window: {exc}",
                file=sys.stderr,
            )
            cap.release()
            detector.close()
            return 1

    # Statistics
    frame_count = 0
    total_candidates = 0
    selection_changes = 0
    prev_selected_center: tuple[float, float] | None = None
    frames_with_multiple = 0
    max_candidates_seen = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            timestamp_ms = int(frame_count * frame_interval_ms)
            candidates = detector.detect_all(frame, timestamp_ms)
            num_candidates = len(candidates)

            total_candidates += num_candidates
            max_candidates_seen = max(
                max_candidates_seen, num_candidates
            )
            if num_candidates > 1:
                frames_with_multiple += 1

            # Select primary
            primary_result = detector.select_primary(candidates)
            current_center = detector.subject.last_center

            # Track selection changes
            if (
                prev_selected_center is not None
                and current_center is not None
            ):
                dist = (
                    (current_center[0] - prev_selected_center[0]) ** 2
                    + (current_center[1] - prev_selected_center[1]) ** 2
                ) ** 0.5
                if dist > 0.15:
                    selection_changes += 1
            prev_selected_center = current_center

            # Print per-frame info (every 30 frames to reduce spam)
            if frame_count % 30 == 0:
                areas = [f"{c.body_area:.4f}" for c in candidates]
                state = detector.track_state.value
                lost = detector.lost_frame_count
                conf = detector.subject.confidence
                sid = detector.subject.subject_id
                print(
                    f"  Frame {frame_count:>5}: "
                    f"{num_candidates} cand, "
                    f"subj={sid}, "
                    f"state={state}, "
                    f"conf={conf:.2f}, "
                    f"lost={lost}, "
                    f"areas=[{', '.join(areas)}]"
                )

            # Preview mode
            if preview and candidates:
                display = frame.copy()

                # Draw all candidates
                for i, cand in enumerate(candidates):
                    is_primary = (
                        cand.pose_result is primary_result
                    )
                    color = (
                        COLOR_PRIMARY if is_primary
                        else COLOR_SECONDARY
                    )
                    label = (
                        f"PRIMARY #{i}"
                        if is_primary
                        else f"Person #{i}"
                    )
                    draw_candidate_skeleton(
                        display, cand, color, label
                    )

                # Info overlay
                h_frame, w_frame = display.shape[:2]
                overlay = display.copy()
                cv2.rectangle(
                    overlay, (0, 0), (w_frame, 60),
                    COLOR_PANEL_BG, -1,
                )
                cv2.addWeighted(
                    overlay, 0.7, display, 0.3, 0, display
                )
                cv2.putText(
                    display,
                    f"Frame {frame_count}/{total_frames} | "
                    f"Candidates: {num_candidates}",
                    (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, COLOR_TEXT, 1,
                )
                # Track state with color coding
                state = detector.track_state
                if state == TrackState.TRACKING:
                    state_color = COLOR_PRIMARY
                elif state == TrackState.OCCLUDED:
                    state_color = (0, 255, 255)  # Yellow
                elif state == TrackState.LOST:
                    state_color = (0, 0, 255)  # Red
                elif state == TrackState.UNCERTAIN:
                    state_color = (0, 200, 255)  # Orange
                else:
                    state_color = COLOR_TEXT
                subj = detector.subject
                state_text = (
                    f"SUBJ:{subj.subject_id} | "
                    f"{state.value} | "
                    f"conf={subj.confidence:.2f} | "
                    f"lost={subj.lost_frame_count}"
                )
                cv2.putText(
                    display,
                    state_text,
                    (10, 45),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, state_color, 1,
                )

                cv2.imshow(WINDOW_NAME, display)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    break

                try:
                    prop = cv2.getWindowProperty(
                        WINDOW_NAME, cv2.WND_PROP_VISIBLE
                    )
                    if prop < 1:
                        break
                except cv2.error:
                    break

            frame_count += 1

    except KeyboardInterrupt:
        print("\n  Interrupted.")
    finally:
        cap.release()
        detector.close()
        if preview:
            cv2.destroyAllWindows()

    # Summary
    avg_candidates = (
        total_candidates / frame_count if frame_count > 0 else 0.0
    )

    print()
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Total frames processed:    {frame_count}")
    print(f"  Total candidates detected: {total_candidates}")
    print(f"  Average candidates/frame:  {avg_candidates:.2f}")
    print(f"  Max candidates in a frame: {max_candidates_seen}")
    print(f"  Frames with multiple:      {frames_with_multiple}")
    print(f"  Selection changes:         {selection_changes}")
    print("=" * 60)

    return 0


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Multi-Person Detection Diagnostic — OpenDance AI",
    )
    parser.add_argument("video_path", help="Path to video file")
    parser.add_argument(
        "--max-poses",
        type=int,
        default=5,
        help="Maximum number of poses to detect (default: 5)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Show visual preview with detected people",
    )

    args = parser.parse_args()

    video_path = Path(args.video_path)
    if not video_path.exists():
        print(
            f"ERROR: Video not found: {args.video_path}",
            file=sys.stderr,
        )
        return 1

    return run_diagnostic(
        video_path,
        max_poses=args.max_poses,
        preview=args.preview,
    )


if __name__ == "__main__":
    sys.exit(main())
