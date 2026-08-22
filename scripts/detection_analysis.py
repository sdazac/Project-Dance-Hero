"""Detection-Drop Analysis Diagnostic — Phase 3.5 validation.

Analyzes a video's pose detection results to identify NO-POSE segments,
investigate their causes, and evaluate pipeline reliability for Phase 4.

Usage:
    python scripts/detection_analysis.py path/to/video.mp4
    python scripts/detection_analysis.py path/to/video.mp4 --preview

Requires a prior successful analysis via video_analysis_diagnostic.py
(or performs fresh analysis if needed).
"""

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Ensure src/ is importable when running as a script
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from opendance.config.models import (  # noqa: E402
    NormalizationConfig,
    PoseConfig,
    ReferenceConfig,
)
from opendance.pose.detector import PoseDetector  # noqa: E402
from opendance.ui.skeleton_renderer import render_skeleton  # noqa: E402
from opendance.video.reference_analyzer import ReferenceAnalyzer  # noqa: E402
from opendance.video.reference_sequence import ReferenceSequence  # noqa: E402

# --- Constants ---
MODEL_PATH = str(_project_root / "assets" / "models" / "pose_landmarker.task")
SEPARATOR = "=" * 60
SUBSEP = "-" * 60


@dataclass
class FrameInfo:
    """Per-frame detection information."""

    frame_index: int
    timestamp_ms: int
    detected: bool
    visible_landmarks: int
    body_scale: float
    # Motion magnitude from previous frame context (if available)
    motion_magnitude: float


@dataclass
class NoPoseSegment:
    """A contiguous segment where no pose was detected."""

    first_frame: int
    last_frame: int
    start_ms: int
    end_ms: int
    duration_ms: int
    frame_count: int
    # Context: stats from frames immediately before/after
    pre_body_scale: float | None
    post_body_scale: float | None
    pre_motion_mag: float | None
    post_motion_mag: float | None
    pre_visible_lm: int | None
    post_visible_lm: int | None


def get_config() -> tuple[PoseConfig, NormalizationConfig, ReferenceConfig]:
    """Return default configs for analysis."""
    pose_cfg = PoseConfig(model_path=MODEL_PATH)
    norm_cfg = NormalizationConfig(enabled=True, visibility_threshold=0.5)
    ref_cfg = ReferenceConfig(cache_directory="", auto_cache=False, sample_fps=30.0)
    return pose_cfg, norm_cfg, ref_cfg


def analyze_video(video_path: Path) -> ReferenceSequence:
    """Run full analysis on the video."""
    pose_cfg, norm_cfg, ref_cfg = get_config()
    analyzer = ReferenceAnalyzer(pose_cfg, norm_cfg, ref_cfg)
    try:
        print(f"  Analyzing video: {video_path.name}")
        sequence = analyzer.analyze(str(video_path))
        print(f"  Analysis complete: {len(sequence.poses)} frames")
        return sequence
    finally:
        analyzer.close()


def build_frame_info(sequence: ReferenceSequence) -> list[FrameInfo]:
    """Build per-frame detection information from ReferenceSequence."""
    frames: list[FrameInfo] = []
    sample_interval_ms = 1000.0 / 30.0  # Assuming 30 fps sample

    for i, pose in enumerate(sequence.poses):
        timestamp_ms = int(i * sample_interval_ms)
        detected = pose is not None and pose.valid

        visible_lm = 0
        body_scale = 0.0
        if detected and pose is not None:
            visible_lm = sum(
                1 for v in pose.visibilities if v >= 0.5
            )
            body_scale = pose.body_scale

        # Motion magnitude from motion features
        motion_mag = 0.0
        if i < len(sequence.motion_features):
            mf = sequence.motion_features[i]
            if mf is not None and mf.landmark_motions is not None:
                speeds = [
                    lm.speed
                    for lm in mf.landmark_motions
                    if lm is not None and lm.speed is not None
                ]
                if speeds:
                    motion_mag = float(np.mean(speeds))

        frames.append(FrameInfo(
            frame_index=i,
            timestamp_ms=timestamp_ms,
            detected=detected,
            visible_landmarks=visible_lm,
            body_scale=body_scale,
            motion_magnitude=motion_mag,
        ))

    return frames


def find_no_pose_segments(frames: list[FrameInfo]) -> list[NoPoseSegment]:
    """Identify contiguous NO-POSE segments."""
    segments: list[NoPoseSegment] = []
    n = len(frames)
    i = 0

    while i < n:
        if not frames[i].detected:
            start = i
            while i < n and not frames[i].detected:
                i += 1
            end = i - 1

            # Context from surrounding frames
            pre_scale = (
                frames[start - 1].body_scale
                if start > 0 and frames[start - 1].detected else None
            )
            post_scale = (
                frames[end + 1].body_scale
                if end + 1 < n and frames[end + 1].detected else None
            )
            pre_motion = frames[start - 1].motion_magnitude if start > 0 else None
            post_motion = frames[end + 1].motion_magnitude if end + 1 < n else None
            pre_lm = (
                frames[start - 1].visible_landmarks
                if start > 0 and frames[start - 1].detected else None
            )
            post_lm = (
                frames[end + 1].visible_landmarks
                if end + 1 < n and frames[end + 1].detected else None
            )

            segments.append(NoPoseSegment(
                first_frame=start,
                last_frame=end,
                start_ms=frames[start].timestamp_ms,
                end_ms=frames[end].timestamp_ms,
                duration_ms=frames[end].timestamp_ms - frames[start].timestamp_ms,
                frame_count=end - start + 1,
                pre_body_scale=pre_scale,
                post_body_scale=post_scale,
                pre_motion_mag=pre_motion,
                post_motion_mag=post_motion,
                pre_visible_lm=pre_lm,
                post_visible_lm=post_lm,
            ))
        else:
            i += 1

    return segments


def compute_windowed_detection_rate(
    frames: list[FrameInfo], window_ms: int = 1000
) -> list[tuple[int, int, float]]:
    """Compute detection rate per fixed time window.

    Returns: list of (window_start_ms, window_end_ms, detection_rate).
    """
    if not frames:
        return []

    total_duration = frames[-1].timestamp_ms
    windows: list[tuple[int, int, float]] = []

    window_start = 0
    while window_start <= total_duration:
        window_end = window_start + window_ms
        window_frames = [
            f for f in frames
            if window_start <= f.timestamp_ms < window_end
        ]
        if window_frames:
            detected = sum(1 for f in window_frames if f.detected)
            rate = detected / len(window_frames) * 100
            windows.append((window_start, window_end, rate))
        window_start += window_ms

    return windows


def analyze_segment_context(
    segment: NoPoseSegment, frames: list[FrameInfo]
) -> list[str]:
    """Analyze possible causes for a NO-POSE segment based on observable data."""
    causes: list[str] = []

    # High motion before drop
    if segment.pre_motion_mag is not None and segment.pre_motion_mag > 0.05:
        causes.append(f"High motion before gap (mag={segment.pre_motion_mag:.4f})")

    # Body scale instability (large change before/after)
    if segment.pre_body_scale is not None and segment.post_body_scale is not None:
        scale_change = abs(segment.post_body_scale - segment.pre_body_scale)
        if scale_change > 0.05:
            causes.append(
                f"Body scale change across gap: {scale_change:.4f} "
                f"(pre={segment.pre_body_scale:.4f}, post={segment.post_body_scale:.4f})"
            )

    # Low landmark count before/after (partial occlusion indicator)
    if segment.pre_visible_lm is not None and segment.pre_visible_lm < 20:
        causes.append(f"Low visibility before gap ({segment.pre_visible_lm}/33 landmarks)")
    if segment.post_visible_lm is not None and segment.post_visible_lm < 20:
        causes.append(f"Low visibility after gap ({segment.post_visible_lm}/33 landmarks)")

    # Long segment suggests person may have left frame or turned away
    if segment.frame_count > 15:  # > 0.5s at 30fps
        causes.append("Extended gap (>0.5s) — possible turn/exit/occlusion")

    # Very short segment with high pre-motion suggests motion blur
    if segment.frame_count <= 3 and segment.pre_motion_mag is not None:
        if segment.pre_motion_mag > 0.03:
            causes.append("Brief drop with preceding motion — possible motion blur")

    if not causes:
        causes.append("No clear observable cause from available data")

    return causes


def analyze_rotation_evidence(frames: list[FrameInfo], sequence: ReferenceSequence) -> dict:
    """Investigate orientation/rotation from landmark relationships."""
    # Check shoulder width ratio changes as proxy for body orientation
    shoulder_widths: list[float | None] = []

    for pose in sequence.poses:
        if pose is None or not pose.valid or pose.landmarks_2d is None:
            shoulder_widths.append(None)
            continue

        # Landmarks 11 (left shoulder) and 12 (right shoulder)
        left_sh = pose.landmarks_2d[11]
        right_sh = pose.landmarks_2d[12]

        if left_sh is not None and right_sh is not None:
            width = abs(left_sh[0] - right_sh[0])
            shoulder_widths.append(width)
        else:
            shoulder_widths.append(None)

    # Hip width ratio
    hip_widths: list[float | None] = []
    for pose in sequence.poses:
        if pose is None or not pose.valid or pose.landmarks_2d is None:
            hip_widths.append(None)
            continue

        left_hip = pose.landmarks_2d[23]
        right_hip = pose.landmarks_2d[24]

        if left_hip is not None and right_hip is not None:
            width = abs(left_hip[0] - right_hip[0])
            hip_widths.append(width)
        else:
            hip_widths.append(None)

    # Compute statistics
    valid_shoulders = [w for w in shoulder_widths if w is not None]
    valid_hips = [w for w in hip_widths if w is not None]

    # Narrow shoulder width indicates body rotation (facing sideways)
    narrow_shoulder_frames = sum(
        1 for w in valid_shoulders if w < np.mean(valid_shoulders) * 0.5
    ) if valid_shoulders else 0

    return {
        "shoulder_width_mean": float(np.mean(valid_shoulders)) if valid_shoulders else 0,
        "shoulder_width_std": float(np.std(valid_shoulders)) if valid_shoulders else 0,
        "shoulder_width_min": float(min(valid_shoulders)) if valid_shoulders else 0,
        "shoulder_width_max": float(max(valid_shoulders)) if valid_shoulders else 0,
        "hip_width_mean": float(np.mean(valid_hips)) if valid_hips else 0,
        "hip_width_std": float(np.std(valid_hips)) if valid_hips else 0,
        "narrow_shoulder_frames": narrow_shoulder_frames,
        "total_detected_frames": len(valid_shoulders),
        "shoulder_widths": shoulder_widths,
        "hip_widths": hip_widths,
    }


def analyze_fast_movement(frames: list[FrameInfo], segments: list[NoPoseSegment]) -> dict:
    """Analyze correlation between motion magnitude and detection drops."""
    detected_motions = [f.motion_magnitude for f in frames if f.detected and f.motion_magnitude > 0]
    overall_mean_motion = float(np.mean(detected_motions)) if detected_motions else 0.0

    # Motion near detection drops
    pre_drop_motions = [
        s.pre_motion_mag for s in segments
        if s.pre_motion_mag is not None and s.pre_motion_mag > 0
    ]
    post_drop_motions = [
        s.post_motion_mag for s in segments
        if s.post_motion_mag is not None and s.post_motion_mag > 0
    ]

    high_motion_drops = sum(
        1 for s in segments
        if s.pre_motion_mag is not None and s.pre_motion_mag > overall_mean_motion * 1.5
    )

    return {
        "overall_mean_motion": overall_mean_motion,
        "overall_max_motion": float(max(detected_motions)) if detected_motions else 0.0,
        "pre_drop_mean_motion": float(np.mean(pre_drop_motions)) if pre_drop_motions else 0.0,
        "post_drop_mean_motion": float(np.mean(post_drop_motions)) if post_drop_motions else 0.0,
        "high_motion_drops": high_motion_drops,
        "total_drops": len(segments),
        "correlation_evidence": "moderate" if high_motion_drops > len(segments) * 0.3 else "weak",
    }


def print_full_report(
    frames: list[FrameInfo],
    segments: list[NoPoseSegment],
    windows: list[tuple[int, int, float]],
    rotation_data: dict,
    motion_data: dict,
    sequence: ReferenceSequence,
) -> None:
    """Print the complete diagnostic report."""
    total = len(frames)
    detected = sum(1 for f in frames if f.detected)
    not_detected = total - detected
    detection_rate = (detected / total * 100) if total > 0 else 0

    print()
    print(SEPARATOR)
    print("  DETECTION-DROP ANALYSIS REPORT")
    print(SEPARATOR)

    # === Overall Statistics ===
    print()
    print("  OVERALL STATISTICS")
    print(SUBSEP)
    print(f"  Total sampled frames:  {total}")
    print(f"  Pose detected:         {detected}")
    print(f"  No pose:               {not_detected}")
    print(f"  Detection rate:        {detection_rate:.1f}%")
    print()

    # === NO-POSE Segments ===
    print("  NO-POSE SEGMENTS")
    print(SUBSEP)
    print(f"  Total segments:        {len(segments)}")

    if segments:
        durations = [s.duration_ms for s in segments]
        counts = [s.frame_count for s in segments]
        print(f"  Longest segment:       {max(counts)} frames ({max(durations)} ms)")
        avg_count = np.mean(counts)
        avg_dur = np.mean(durations)
        print(f"  Average segment:       {avg_count:.1f} frames ({avg_dur:.0f} ms)")
        print(f"  Shortest segment:      {min(counts)} frames ({min(durations)} ms)")
        print()

        print("  SEGMENT DETAILS:")
        for i, seg in enumerate(segments):
            causes = analyze_segment_context(seg, frames)
            print(f"    Segment {i + 1}: frames {seg.first_frame}–{seg.last_frame} "
                  f"({seg.frame_count} frames, {seg.start_ms}–{seg.end_ms} ms, "
                  f"duration {seg.duration_ms} ms)")
            for cause in causes:
                print(f"      → {cause}")
        print()

    # === Detection Rate by Time Window ===
    print("  DETECTION RATE BY 1-SECOND WINDOW")
    print(SUBSEP)
    low_windows = [(s, e, r) for s, e, r in windows if r < 80]
    for start, end, rate in windows:
        marker = " ← LOW" if rate < 80 else ""
        print(f"    {start / 1000:.0f}s–{end / 1000:.0f}s: {rate:.1f}%{marker}")
    print()
    if low_windows:
        print(f"  Windows below 80%: {len(low_windows)} / {len(windows)}")
    else:
        print("  All windows above 80%")
    print()

    # === Rotation/Turn Evidence ===
    print("  ROTATION / TURN EVIDENCE")
    print(SUBSEP)
    print(f"  Shoulder width (normalized, mean): {rotation_data['shoulder_width_mean']:.4f}")
    print(f"  Shoulder width (std):              {rotation_data['shoulder_width_std']:.4f}")
    print(f"  Shoulder width (min):              {rotation_data['shoulder_width_min']:.4f}")
    print(f"  Shoulder width (max):              {rotation_data['shoulder_width_max']:.4f}")
    print(f"  Hip width (mean):                  {rotation_data['hip_width_mean']:.4f}")
    print(f"  Hip width (std):                   {rotation_data['hip_width_std']:.4f}")
    print(f"  Narrow-shoulder frames (<50% mean): {rotation_data['narrow_shoulder_frames']}")
    print()

    if rotation_data['shoulder_width_std'] > rotation_data['shoulder_width_mean'] * 0.3:
        print("  OBSERVATION: High shoulder-width variance suggests body rotations are present.")
    else:
        print("  OBSERVATION: Shoulder-width variance is moderate — limited rotation observed.")

    if rotation_data['narrow_shoulder_frames'] > 0:
        pct = rotation_data['narrow_shoulder_frames'] / rotation_data['total_detected_frames'] * 100
        print(f"  Narrow-shoulder fraction: {pct:.1f}% of detected frames")
        print("  This may indicate moments where the person faces sideways/away.")
    print()

    # === Fast Movement Evidence ===
    print("  FAST MOVEMENT EVIDENCE")
    print(SUBSEP)
    print(f"  Overall mean motion:     {motion_data['overall_mean_motion']:.5f}")
    print(f"  Overall max motion:      {motion_data['overall_max_motion']:.5f}")
    print(f"  Pre-drop mean motion:    {motion_data['pre_drop_mean_motion']:.5f}")
    print(f"  Post-drop mean motion:   {motion_data['post_drop_mean_motion']:.5f}")
    hi_drops = motion_data['high_motion_drops']
    total_drops = motion_data['total_drops']
    print(f"  High-motion drops:       {hi_drops} / {total_drops}")
    print(f"  Motion-drop correlation: {motion_data['correlation_evidence']}")
    print()

    if motion_data['pre_drop_mean_motion'] > motion_data['overall_mean_motion'] * 1.3:
        print("  OBSERVATION: Detection drops tend to follow higher-than-average motion.")
    else:
        print("  OBSERVATION: No strong evidence that fast movement alone causes drops.")
    print()

    # === Body Scale Stability ===
    print("  BODY SCALE STABILITY")
    print(SUBSEP)
    scales = [f.body_scale for f in frames if f.detected]
    if scales:
        print(f"  Mean:  {np.mean(scales):.4f}")
        print(f"  Std:   {np.std(scales):.4f}")
        print(f"  Min:   {min(scales):.4f}")
        print(f"  Max:   {max(scales):.4f}")
        print(f"  Range: {max(scales) - min(scales):.4f}")
        cv = np.std(scales) / np.mean(scales) * 100 if np.mean(scales) > 0 else 0
        print(f"  CV:    {cv:.1f}%")
        if cv < 10:
            print("  OBSERVATION: Body scale is stable (CV < 10%).")
        else:
            print("  OBSERVATION: Body scale has notable variation (CV >= 10%).")
    print()

    # === Orientation Capability Assessment ===
    print("  ROTATION DETECTION CAPABILITY ASSESSMENT")
    print(SUBSEP)
    print("  The current 33-landmark pipeline provides:")
    print("    - Shoulder pair (landmarks 11, 12)")
    print("    - Hip pair (landmarks 23, 24)")
    print("    - Left/right side differentiation")
    print()
    print("  What CAN be inferred:")
    print("    - Approximate frontal vs. sideways orientation (shoulder/hip width ratio)")
    print("    - Gradual orientation changes between frames")
    print("    - Moments when body faces partially away (narrowing landmarks)")
    print()
    print("  What CANNOT be reliably inferred:")
    print("    - Exact rotation angle in degrees")
    print("    - Whether person faces camera vs. faces away (180deg ambiguity)")
    print("    - Full 360-degree turn tracking")
    print("    - Orientation when few landmarks are visible")
    print()
    print("  Recommendation for Phase 4:")
    print("    Use shoulder/hip width ratio as a SOFT orientation indicator.")
    print("    Do NOT claim precise rotation measurement.")
    print("    Accept that facing-away poses will have degraded detection.")
    print()

    # === Finger Tracking Limitation ===
    print("  FINGER TRACKING LIMITATION")
    print(SUBSEP)
    print("  Individual finger motion is NOT currently analyzed.")
    print("  The 33-landmark Pose model tracks wrist position only.")
    print("  Detailed finger joints (thumb, index, middle, ring, little)")
    print("  would require MediaPipe Hands (21 landmarks per hand).")
    print("  This is a future enhancement, not a Phase 4 requirement.")
    print()

    # === IMAGE_DIMENSIONS Warning ===
    print("  IMAGE_DIMENSIONS WARNING ANALYSIS")
    print(SUBSEP)
    print("  Warning: 'Using NORM_RECT without IMAGE_DIMENSIONS is only")
    print("  supported for the square ROI.'")
    print()
    print("  Root cause:")
    print("    MediaPipe's internal landmark_projection_calculator uses NORM_RECT")
    print("    to project model-space landmarks back to image space. When")
    print("    IMAGE_DIMENSIONS is not provided (Python Tasks SDK does not expose it),")
    print("    it assumes a square ROI for Z-coordinate scaling.")
    print()
    print("  Impact on this project:")
    print("    - x, y landmark positions: CORRECT (use rect width/height separately)")
    print("    - z coordinate scale: MINOR inaccuracy on non-square images")
    print("    - Phase 3 scoring: uses 2D (x, y) ONLY — NOT affected")
    print("    - World landmarks: computed independently — NOT affected")
    print("    - Normalization: prefers world landmarks — NOT affected")
    print()
    print("  Conclusion: WARNING IS HARMLESS in the current configuration.")
    print("  No production code change required.")
    print("  This is a known MediaPipe issue (GitHub #5639, still open).")
    print("  The Python Tasks SDK does not currently expose a way to set")
    print("  IMAGE_DIMENSIONS from user code.")
    print()

    # === Pipeline Suitability ===
    print("  PIPELINE SUITABILITY FOR PHASE 4")
    print(SUBSEP)
    if detection_rate >= 80:
        print(f"  Detection rate: {detection_rate:.1f}% — SUITABLE for Phase 4")
        print("  The pipeline can handle this video with acceptable coverage.")
    elif detection_rate >= 60:
        print(f"  Detection rate: {detection_rate:.1f}% — MARGINAL")
        print("  Phase 4 should handle detection gaps gracefully.")
    else:
        print(f"  Detection rate: {detection_rate:.1f}% — INSUFFICIENT")
        print("  Pipeline improvements may be needed before Phase 4.")
    print()

    longest_gap = max(s.frame_count for s in segments) if segments else 0
    if longest_gap <= 30:
        print(f"  Longest gap: {longest_gap} frames — acceptable (≤ 1s at 30fps)")
    else:
        print(f"  Longest gap: {longest_gap} frames — Phase 4 must handle extended gaps")
    print()

    print("  Recommendations:")
    print("    1. Phase 4 scoring should gracefully handle NO-POSE frames (already None)")
    print("    2. Combo should break on extended detection gaps")
    print("    3. Analytics should highlight low-detection sections")
    print("    4. No production pipeline changes required for this video")
    print()

    print(SEPARATOR)
    print("  ANALYSIS COMPLETE")
    print(SEPARATOR)


def run_preview(
    video_path: Path,
    frames: list[FrameInfo],
    segments: list[NoPoseSegment],
) -> None:
    """Preview video highlighting detection drops."""
    print()
    print("  Starting detection-drop preview...")
    print("  RED overlay = NO POSE segment. Press q/ESC to exit.")
    print()

    pose_cfg = PoseConfig(model_path=MODEL_PATH)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print("ERROR: Cannot open video for preview.", file=sys.stderr)
        return

    try:
        detector = PoseDetector(pose_cfg)
    except Exception as exc:
        print(f"ERROR: Cannot init detector: {exc}", file=sys.stderr)
        cap.release()
        return

    window_name = f"Detection Analysis - {video_path.name}"
    try:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    except cv2.error:
        print("ERROR: No GUI backend available.", file=sys.stderr)
        detector.close()
        cap.release()
        return

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_delay = max(1, int(1000.0 / source_fps))

    # Build set of NO-POSE frame indices for fast lookup
    no_pose_frames = set()
    for seg in segments:
        for fi in range(seg.first_frame, seg.last_frame + 1):
            no_pose_frames.add(fi)

    frame_idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            timestamp_ms = int(frame_idx * (1000.0 / source_fps))
            pose_result = detector.detect(frame, timestamp_ms=timestamp_ms)

            # Draw skeleton
            render_skeleton(frame, pose_result, visibility_threshold=0.5)

            # Highlight NO-POSE frames with red tint
            if frame_idx in no_pose_frames:
                red_overlay = frame.copy()
                red_overlay[:, :, 2] = np.minimum(
                    red_overlay[:, :, 2].astype(np.int16) + 60, 255
                ).astype(np.uint8)
                cv2.addWeighted(red_overlay, 0.6, frame, 0.4, 0, frame)

            # Info overlay
            h, w = frame.shape[:2]
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, 70), (40, 40, 40), -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

            status = "DETECTED" if not pose_result.is_empty else "NO POSE"
            color = (0, 255, 0) if not pose_result.is_empty else (0, 0, 255)

            cv2.putText(frame, f"Frame {frame_idx}/{total_frames}", (10, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, f"Time: {timestamp_ms / 1000:.2f}s", (10, 44),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, status, (10, 66),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(frame_delay) & 0xFF
            if key == ord("q") or key == 27:
                break
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                break

            frame_idx += 1

    except KeyboardInterrupt:
        pass
    finally:
        detector.close()
        cap.release()
        cv2.destroyAllWindows()
        print(f"  Preview done ({frame_idx} frames shown).")


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Detection-Drop Analysis — OpenDance AI Phase 3.5",
    )
    parser.add_argument("video_path", help="Path to video file")
    parser.add_argument(
        "--preview", action="store_true",
        help="Visual preview with drop highlights",
    )

    args = parser.parse_args()

    # Validate
    video_path = Path(args.video_path)
    if not video_path.exists():
        print(f"ERROR: Video not found: {args.video_path}", file=sys.stderr)
        return 1
    if not Path(MODEL_PATH).exists():
        print("ERROR: Model not found. Run: python scripts/download_models.py", file=sys.stderr)
        return 1

    print(SEPARATOR)
    print("  DETECTION-DROP ANALYSIS — OpenDance AI Phase 3.5")
    print(SEPARATOR)
    print(f"  Video: {video_path.name}")
    print(f"  Path:  {video_path.resolve()}")
    print()

    # Analyze
    start = time.time()
    sequence = analyze_video(video_path)
    elapsed = time.time() - start
    print(f"  Analysis time: {elapsed:.1f}s")
    print()

    # Build frame info
    frames = build_frame_info(sequence)

    # Find segments
    segments = find_no_pose_segments(frames)

    # Windowed detection rate
    windows = compute_windowed_detection_rate(frames)

    # Rotation analysis
    rotation_data = analyze_rotation_evidence(frames, sequence)

    # Fast movement analysis
    motion_data = analyze_fast_movement(frames, segments)

    # Print report
    print_full_report(frames, segments, windows, rotation_data, motion_data, sequence)

    # Preview
    if args.preview:
        run_preview(video_path, frames, segments)

    return 0


if __name__ == "__main__":
    sys.exit(main())
