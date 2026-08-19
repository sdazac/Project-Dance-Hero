"""Subject Tracking Visual Validation — OpenDance AI.

Replays a video showing all detected candidates with the tracked subject
highlighted. Allows frame-by-frame inspection of identity persistence.

Usage:
    python scripts/subject_tracking_replay.py path/to/video.mp4
    python scripts/subject_tracking_replay.py path/to/video.mp4 --save out.mp4

Controls:
    SPACE       pause/resume
    RIGHT       next frame (paused)
    LEFT        previous frame (paused)
    TAB         toggle other candidates visibility
    T           toggle center trail
    I           toggle detailed info panel
    Q / ESC     exit
"""

import argparse
import sys
import time
from pathlib import Path

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
WINDOW = "Subject Tracking Replay"

# Colors BGR
C_PRIMARY = (0, 255, 0)       # Green
C_OCCLUDED = (0, 255, 255)    # Yellow
C_LOST = (0, 0, 255)          # Red
C_UNCERTAIN = (0, 165, 255)   # Orange
C_TRAIL = (255, 0, 200)       # Magenta
C_TEXT = (255, 255, 255)
C_PANEL = (30, 30, 30)
C_OTHERS = [
    (255, 100, 0),   # Blue-ish
    (0, 200, 200),   # Teal
    (200, 0, 200),   # Purple
    (100, 200, 0),   # Lime
    (200, 100, 100), # Light blue
]


def _draw_candidate(
    frame: np.ndarray,
    cand: PoseCandidate,
    color: tuple[int, int, int],
    label: str,
    thickness: int = 1,
    vis_threshold: float = 0.5,
) -> None:
    """Draw landmarks + bounding box for a candidate."""
    h, w = frame.shape[:2]
    lms = cand.pose_result.landmarks

    # Draw landmarks
    for lm in lms:
        if lm.visibility >= vis_threshold:
            px, py = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (px, py), 3, color, -1)

    # Bounding box from visible landmarks
    visible = [
        (lm.x, lm.y) for lm in lms if lm.visibility >= vis_threshold
    ]
    if len(visible) >= 3:
        xs = [p[0] for p in visible]
        ys = [p[1] for p in visible]
        x1, y1 = int(min(xs) * w), int(min(ys) * h)
        x2, y2 = int(max(xs) * w), int(max(ys) * h)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
        cv2.putText(
            frame, label, (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1,
        )


def _draw_trail(
    frame: np.ndarray,
    centers: list[tuple[float, float]],
) -> None:
    """Draw motion trail from center history."""
    h, w = frame.shape[:2]
    pts = [(int(cx * w), int(cy * h)) for cx, cy in centers]
    for i in range(1, len(pts)):
        alpha = i / len(pts)
        color = (
            int(C_TRAIL[0] * alpha),
            int(C_TRAIL[1] * alpha),
            int(C_TRAIL[2] * alpha),
        )
        cv2.line(frame, pts[i - 1], pts[i], color, 2)


def _state_color(state: TrackState) -> tuple[int, int, int]:
    if state == TrackState.TRACKING:
        return C_PRIMARY
    elif state == TrackState.OCCLUDED:
        return C_OCCLUDED
    elif state == TrackState.LOST:
        return C_LOST
    elif state == TrackState.UNCERTAIN:
        return C_UNCERTAIN
    return C_TEXT


def run(video_path: Path, save_path: str | None = None) -> int:
    """Main replay loop."""
    if not Path(MODEL_PATH).exists():
        print("ERROR: Model not found. Run: python scripts/download_models.py")
        return 1

    config = PoseConfig(
        model_path=MODEL_PATH,
        skeleton_visibility_threshold=0.5,
        max_poses=5,
    )
    detector = MultiPoseDetector(config)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"ERROR: Cannot open {video_path}")
        return 1

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    vid_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vid_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"  Video: {video_path.name}")
    print(f"  Resolution: {vid_w}x{vid_h}, FPS: {fps:.2f}")
    print(f"  Frames: {total_frames}")
    print()
    print("  Loading frames...")

    frames: list[np.ndarray] = []
    while True:
        ret, frm = cap.read()
        if not ret or frm is None:
            break
        frames.append(frm)
    cap.release()
    print(f"  Loaded {len(frames)} frames.")
    print()
    print("  Processing detection for all frames...")

    # Pre-process all detection data
    all_candidates: list[list[PoseCandidate]] = []
    all_results: list[tuple[TrackState, float, int, int]] = []
    # (state, confidence, lost_count, matched_candidate_idx)
    prev_matched_idx = -1
    candidate_idx_changes = 0
    recoveries = 0
    prev_state = TrackState.UNLOCKED

    for i, frame in enumerate(frames):
        ts = int(i * (1000.0 / fps))
        cands = detector.detect_all(frame, ts)
        primary = detector.select_primary(cands)
        all_candidates.append(cands)

        state = detector.track_state
        conf = detector.subject.confidence
        lost = detector.lost_frame_count

        # Determine which candidate index was matched
        matched_idx = -1
        if not primary.is_empty:
            for ci, c in enumerate(cands):
                if c.pose_result is primary:
                    matched_idx = ci
                    break

        # Track candidate index changes
        if (
            matched_idx >= 0
            and prev_matched_idx >= 0
            and matched_idx != prev_matched_idx
        ):
            candidate_idx_changes += 1

        # Track recoveries
        if (
            state == TrackState.TRACKING
            and prev_state in (TrackState.LOST, TrackState.OCCLUDED)
        ):
            recoveries += 1

        prev_matched_idx = matched_idx if matched_idx >= 0 else prev_matched_idx
        prev_state = state
        all_results.append((state, conf, lost, matched_idx))

        if i % 500 == 0:
            print(f"    Processed {i}/{len(frames)}")

    print("  Detection complete.")
    print()

    # Writer
    writer = None
    if save_path:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
        writer = cv2.VideoWriter(save_path, fourcc, fps, (vid_w, vid_h))

    # Display
    try:
        cv2.namedWindow(WINDOW, cv2.WINDOW_KEEPRATIO)
        max_h = min(vid_h, 900)
        disp_w = int(max_h * vid_w / vid_h)
        cv2.resizeWindow(WINDOW, disp_w, max_h)
    except cv2.error:
        print("ERROR: No GUI backend")
        if writer:
            writer.release()
        return 1

    paused = False
    show_others = True
    show_trail = True
    show_info = True
    frame_idx = 0
    frame_interval = 1.0 / fps
    next_time = time.perf_counter()

    # Stats
    stats_tracking = 0
    stats_occluded = 0
    stats_uncertain = 0
    stats_lost = 0

    try:
        while 0 <= frame_idx < len(frames):
            frame = frames[frame_idx].copy()
            state, conf, lost, matched_idx = all_results[frame_idx]
            cands = all_candidates[frame_idx]

            # Stats
            if state == TrackState.TRACKING:
                stats_tracking += 1
            elif state == TrackState.OCCLUDED:
                stats_occluded += 1
            elif state == TrackState.UNCERTAIN:
                stats_uncertain += 1
            elif state == TrackState.LOST:
                stats_lost += 1

            # Draw other candidates
            if show_others:
                for ci, c in enumerate(cands):
                    if ci == matched_idx:
                        continue
                    col = C_OTHERS[ci % len(C_OTHERS)]
                    _draw_candidate(
                        frame, c, col, f"Cand #{ci}", 1
                    )

            # Draw primary (matched) candidate
            if matched_idx >= 0 and matched_idx < len(cands):
                primary_c = cands[matched_idx]
                sc = _state_color(state)
                _draw_candidate(
                    frame, primary_c, sc,
                    f"SUBJECT [#{matched_idx}]", 2,
                )

            # Trail
            if show_trail:
                trail_start = max(0, frame_idx - 59)
                trail_centers: list[tuple[float, float]] = []
                for ti in range(trail_start, frame_idx + 1):
                    _, _, _, mi = all_results[ti]
                    if mi >= 0 and mi < len(all_candidates[ti]):
                        c = all_candidates[ti][mi]
                        trail_centers.append(
                            (c.center_x, c.center_y)
                        )
                if trail_centers:
                    _draw_trail(frame, trail_centers)

            # Info panel
            panel_h = 100 if show_info else 50
            overlay = frame.copy()
            cv2.rectangle(
                overlay, (0, 0), (vid_w, panel_h), C_PANEL, -1
            )
            cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

            sc = _state_color(state)
            cv2.putText(
                frame,
                f"Frame {frame_idx}/{len(frames)} | "
                f"Cands: {len(cands)}",
                (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, C_TEXT, 1,
            )
            cv2.putText(
                frame,
                f"SUBJ: {detector.subject.subject_id} | "
                f"{state.value} | conf={conf:.2f} | "
                f"lost={lost}",
                (10, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.42, sc, 1,
            )

            if show_info and matched_idx >= 0:
                cv2.putText(
                    frame,
                    f"Matched cand idx: {matched_idx} | "
                    f"area={cands[matched_idx].body_area:.4f}",
                    (10, 58),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, C_TEXT, 1,
                )
                ctr = (
                    cands[matched_idx].center_x,
                    cands[matched_idx].center_y,
                )
                cv2.putText(
                    frame,
                    f"Center: ({ctr[0]:.3f}, {ctr[1]:.3f})",
                    (10, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, C_TEXT, 1,
                )

            # Candidate index change warning
            if frame_idx > 0:
                _, _, _, prev_mi = all_results[frame_idx - 1]
                if (
                    matched_idx >= 0
                    and prev_mi >= 0
                    and matched_idx != prev_mi
                ):
                    cv2.putText(
                        frame,
                        "CANDIDATE INDEX CHANGED",
                        (vid_w // 2 - 120, 95),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 200, 255), 2,
                    )

            # State warnings
            if state == TrackState.LOST:
                cv2.putText(
                    frame,
                    "SUBJECT LOST - NOT SWITCHING",
                    (vid_w // 2 - 150, vid_h - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, C_LOST, 2,
                )
            elif state == TrackState.UNCERTAIN:
                cv2.putText(
                    frame,
                    "IDENTITY UNCERTAIN - NO SWITCH",
                    (vid_w // 2 - 160, vid_h - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, C_UNCERTAIN, 2,
                )
            elif (
                state == TrackState.TRACKING
                and frame_idx > 0
                and all_results[frame_idx - 1][0]
                in (TrackState.LOST, TrackState.OCCLUDED)
            ):
                cv2.putText(
                    frame,
                    f"SUBJECT RECOVERED (conf={conf:.2f})",
                    (vid_w // 2 - 140, vid_h - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, C_PRIMARY, 2,
                )

            # Pause indicator
            if paused:
                cv2.putText(
                    frame, "PAUSED", (vid_w - 90, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 2,
                )

            if writer:
                writer.write(frame)

            cv2.imshow(WINDOW, frame)

            # Timing
            if paused:
                wait = 0
            else:
                next_time += frame_interval
                remaining = next_time - time.perf_counter()
                wait = max(1, int(remaining * 1000))

            key = cv2.waitKey(wait) & 0xFF

            if key == ord("q") or key == 27:
                break
            elif key == ord(" "):
                paused = not paused
                if not paused:
                    next_time = time.perf_counter()
            elif key == 9:  # TAB
                show_others = not show_others
            elif key == ord("t"):
                show_trail = not show_trail
            elif key == ord("i"):
                show_info = not show_info
            elif paused and key in (83, 3):  # Right arrow
                frame_idx += 1
                continue
            elif paused and key in (81, 2):  # Left arrow
                frame_idx = max(0, frame_idx - 1)
                continue

            try:
                if cv2.getWindowProperty(
                    WINDOW, cv2.WND_PROP_VISIBLE
                ) < 1:
                    break
            except cv2.error:
                break

            if not paused:
                frame_idx += 1

    except KeyboardInterrupt:
        pass
    finally:
        if writer:
            writer.release()
            print(f"  Saved: {save_path}")
        cv2.destroyAllWindows()

    # Summary
    print()
    print("=" * 60)
    print("  SUBJECT TRACKING VALIDATION SUMMARY")
    print("=" * 60)
    print(f"  Total frames:            {len(frames)}")
    print(f"  Frames TRACKING:         {stats_tracking}")
    print(f"  Frames OCCLUDED:         {stats_occluded}")
    print(f"  Frames UNCERTAIN:        {stats_uncertain}")
    print(f"  Frames LOST:             {stats_lost}")
    print(f"  Subject ID:              {detector.subject.subject_id}")
    print(f"  Candidate idx changes:   {candidate_idx_changes}")
    print(f"  Recoveries:              {recoveries}")
    print("=" * 60)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Subject Tracking Visual Validation",
    )
    parser.add_argument("video_path", help="Path to video")
    parser.add_argument(
        "--save", metavar="PATH", help="Save replay as MP4"
    )
    args = parser.parse_args()

    video_path = Path(args.video_path)
    if not video_path.exists():
        print(f"ERROR: File not found: {args.video_path}")
        return 1

    return run(video_path, save_path=args.save)


if __name__ == "__main__":
    sys.exit(main())
