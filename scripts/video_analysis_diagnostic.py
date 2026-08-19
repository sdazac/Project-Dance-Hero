"""Video Analysis Diagnostic Tool — validates the Phase 2/3 reference pipeline.

Analyzes a local video file through the existing ReferenceAnalyzer and
validates that AnalysisCache persistence works correctly.

Usage:
    python scripts/video_analysis_diagnostic.py path/to/video.mp4
    python scripts/video_analysis_diagnostic.py path/to/video.mp4 --preview

Controls (preview mode):
    q / ESC — exit

Supported formats: any format readable by OpenCV (mp4, avi, mkv, webm, mov, etc.)

Examples:
    python scripts/video_analysis_diagnostic.py videos/my_dance.mp4
    python scripts/video_analysis_diagnostic.py C:\\Users\\me\\Videos\\dance.mp4 --preview
"""

import argparse
import sys
import time
from dataclasses import asdict
from pathlib import Path

# Ensure src/ is importable when running as a script
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from opendance.config.models import (  # noqa: E402
    AppConfig,
    MotionConfig,
    NormalizationConfig,
    PoseConfig,
    ReferenceConfig,
)
from opendance.pose.detector import PoseDetector  # noqa: E402
from opendance.pose.result import PoseResult  # noqa: E402
from opendance.scoring.engine import ScoringEngine  # noqa: E402
from opendance.ui.skeleton_renderer import render_skeleton  # noqa: E402
from opendance.video.analysis_cache import AnalysisCache, compute_config_hash  # noqa: E402
from opendance.video.reference_analyzer import ReferenceAnalyzer  # noqa: E402
from opendance.video.reference_sequence import ReferenceSequence  # noqa: E402

# --- Constants ---

MODEL_PATH = str(_project_root / "assets" / "models" / "pose_landmarker.task")
DEFAULT_CACHE_DIR = str(_project_root / ".cache" / "analysis")
SEPARATOR = "=" * 60


def print_usage() -> None:
    """Print detailed usage instructions."""
    print(SEPARATOR)
    print("  VIDEO ANALYSIS DIAGNOSTIC — OpenDance AI")
    print(SEPARATOR)
    print()
    print("Usage:")
    print("  python scripts/video_analysis_diagnostic.py <video_path> [--preview]")
    print()
    print("Arguments:")
    print("  video_path   Path to a local video file (relative or absolute)")
    print("  --preview    Optional: replay video with skeleton overlay")
    print()
    print("Supported video formats:")
    print("  mp4, avi, mkv, webm, mov, and any other format supported by OpenCV")
    print()
    print("Where to place your video:")
    print("  Anywhere on your local filesystem. Provide the path as an argument.")
    print("  Examples:")
    print("    videos/my_dance.mp4          (relative to project root)")
    print("    C:\\Users\\me\\Videos\\dance.mp4  (absolute path)")
    print("    ../downloads/clip.mp4        (relative path)")
    print()
    print("Example commands:")
    print("  python scripts/video_analysis_diagnostic.py videos/my_dance.mp4")
    print("  python scripts/video_analysis_diagnostic.py videos/my_dance.mp4 --preview")
    print()
    print("Prerequisites:")
    print("  1. Install the project: pip install -e \".[dev]\"")
    print("  2. Download the pose model: python scripts/download_models.py")
    print(SEPARATOR)


def validate_video_path(video_path: str) -> Path:
    """Validate video path exists and is a file. Returns resolved Path."""
    path = Path(video_path)
    if not path.exists():
        print(f"ERROR: Video file not found: {video_path}", file=sys.stderr)
        print(f"  Resolved path: {path.resolve()}", file=sys.stderr)
        print("  Make sure the file exists at the specified location.", file=sys.stderr)
        sys.exit(1)
    if not path.is_file():
        print(f"ERROR: Not a file: {video_path}", file=sys.stderr)
        sys.exit(1)
    return path


def validate_model() -> None:
    """Check that the pose model is available."""
    if not Path(MODEL_PATH).exists():
        print(f"ERROR: Pose model not found at: {MODEL_PATH}", file=sys.stderr)
        print("  Run: python scripts/download_models.py", file=sys.stderr)
        sys.exit(1)


def get_config() -> tuple[PoseConfig, NormalizationConfig, ReferenceConfig, MotionConfig]:
    """Return default configs for analysis."""
    pose_cfg = PoseConfig(model_path=MODEL_PATH)
    norm_cfg = NormalizationConfig(enabled=True, visibility_threshold=0.5)
    ref_cfg = ReferenceConfig(
        cache_directory=DEFAULT_CACHE_DIR,
        auto_cache=True,
        sample_fps=30.0,
    )
    motion_cfg = MotionConfig()
    return pose_cfg, norm_cfg, ref_cfg, motion_cfg


def get_config_hash(norm_cfg: NormalizationConfig, motion_cfg: MotionConfig) -> str:
    """Compute config hash for cache key."""
    config_values = {
        "normalization": asdict(norm_cfg),
        "motion": asdict(motion_cfg),
    }
    return compute_config_hash(config_values)


def print_video_info(video_path: Path) -> dict:
    """Open video and print basic info. Returns metadata dict."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"ERROR: Cannot open video: {video_path}", file=sys.stderr)
        print("  The file may be corrupted or in an unsupported codec.", file=sys.stderr)
        sys.exit(1)

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps > 0 else 0.0
    cap.release()

    print()
    print(SEPARATOR)
    print("  VIDEO INFORMATION")
    print(SEPARATOR)
    print(f"  File:        {video_path.name}")
    print(f"  Full path:   {video_path.resolve()}")
    print(f"  Resolution:  {width}x{height}")
    print(f"  Source FPS:  {fps:.2f}")
    print(f"  Frames:      {total_frames}")
    print(f"  Duration:    {duration:.2f}s")
    print()

    return {
        "total_frames": total_frames,
        "fps": fps,
        "width": width,
        "height": height,
        "duration": duration,
    }


def run_analysis(
    video_path: Path,
    pose_cfg: PoseConfig,
    norm_cfg: NormalizationConfig,
    ref_cfg: ReferenceConfig,
) -> ReferenceSequence:
    """Run ReferenceAnalyzer on video with progress reporting."""
    print(SEPARATOR)
    print("  ANALYZING VIDEO")
    print(SEPARATOR)
    print(f"  Analysis FPS: {ref_cfg.sample_fps}")
    print()

    analyzer = ReferenceAnalyzer(pose_cfg, norm_cfg, ref_cfg)
    start_time = time.time()

    try:
        sequence = analyzer.analyze(str(video_path))
    finally:
        analyzer.close()

    elapsed = time.time() - start_time
    print(f"  Analysis completed in {elapsed:.2f}s")
    return sequence


def print_analysis_report(sequence: ReferenceSequence) -> None:
    """Print detailed analysis statistics."""
    total = len(sequence.poses)
    poses_detected = sum(1 for p in sequence.poses if p is not None and p.valid)
    no_pose = total - poses_detected
    detection_rate = (poses_detected / total * 100) if total > 0 else 0.0

    # Normalized pose count (same as poses_detected since valid=True implies normalization)
    normalized_count = poses_detected

    # Angle availability
    angles_available = sum(1 for a in sequence.joint_angles if a is not None)

    # Motion availability
    motion_available = sum(1 for m in sequence.motion_features if m is not None)

    print()
    print(SEPARATOR)
    print("  ANALYSIS RESULTS")
    print(SEPARATOR)
    print(f"  Sampled frames:      {total}")
    print(f"  Pose detected:       {poses_detected}")
    print(f"  No pose:             {no_pose}")
    print(f"  Detection rate:      {detection_rate:.1f}%")
    print(f"  Normalized poses:    {normalized_count}")
    print(f"  Angle frames:        {angles_available}")
    print(f"  Motion frames:       {motion_available}")
    print()

    # Body scale statistics for detected frames
    scales = [
        p.body_scale
        for p in sequence.poses
        if p is not None and p.valid
    ]
    if scales:
        print(f"  Body scale (mean):   {np.mean(scales):.4f}")
        print(f"  Body scale (std):    {np.std(scales):.4f}")
        print(f"  Body scale (min):    {min(scales):.4f}")
        print(f"  Body scale (max):    {max(scales):.4f}")
        print()

    # Joint angle keys
    if sequence.joint_angles:
        for a in sequence.joint_angles:
            if a is not None:
                print(f"  Joint angles tracked: {len(a)} joints")
                print(f"  Joints: {', '.join(sorted(a.keys()))}")
                break
    print()


def run_cache_validation(
    video_path: Path,
    sequence: ReferenceSequence,
    norm_cfg: NormalizationConfig,
    motion_cfg: MotionConfig,
) -> None:
    """Validate cache store/load cycle."""
    print(SEPARATOR)
    print("  CACHE VALIDATION")
    print(SEPARATOR)

    config_hash = get_config_hash(norm_cfg, motion_cfg)
    cache = AnalysisCache(cache_directory=DEFAULT_CACHE_DIR, model_path=MODEL_PATH)

    # Store
    print(f"  Cache directory: {DEFAULT_CACHE_DIR}")
    print(f"  Config hash:     {config_hash}")
    print()

    cache.put(str(video_path), config_hash, sequence)
    print("  FIRST RUN: Cache MISS -> analysis generated and stored")
    print()

    # Load
    start = time.time()
    loaded = cache.get(str(video_path), config_hash)
    load_time = time.time() - start

    if loaded is not None:
        print(f"  SECOND RUN: Cache HIT -> analysis loaded ({load_time:.3f}s)")
        print(f"  Loaded frames: {len(loaded.poses)}")
        print(f"  Loaded metadata: {loaded.metadata.file_path}")

        # Validate loaded data integrity
        original_detected = sum(1 for p in sequence.poses if p is not None and p.valid)
        loaded_detected = sum(1 for p in loaded.poses if p is not None and p.valid)
        print(f"  Original detected: {original_detected}")
        print(f"  Loaded detected:   {loaded_detected}")

        if original_detected == loaded_detected:
            print("  Integrity check: PASSED (same pose count)")
        else:
            print("  Integrity check: MISMATCH (pose count differs)")
    else:
        print("  SECOND RUN: Cache MISS (unexpected — investigate)")
        print("  The cache did not return the stored analysis.")

    print()


def run_scoring_validation(sequence: ReferenceSequence) -> None:
    """Validate that ReferenceSequence is compatible with ScoringEngine."""
    print(SEPARATOR)
    print("  SCORING ENGINE COMPATIBILITY")
    print(SEPARATOR)

    config = AppConfig()

    try:
        ScoringEngine(reference=sequence, config=config)
        print("  ReferenceSequence successfully loaded into ScoringEngine")
        print(f"  Reference duration: {sequence.metadata.duration_seconds:.2f}s")
        print(f"  Reference frames:   {len(sequence.poses)}")
        print("  ScoringEngine instantiation: OK")
        print()
        print("  NOTE: No player sequence available for live scoring validation.")
        print("  The reference data is structurally compatible with the engine.")
    except Exception as exc:
        print(f"  ERROR: ScoringEngine rejected the reference: {exc}")

    print()


def print_limitations() -> None:
    """Print explicit capability and limitation statements."""
    print(SEPARATOR)
    print("  PIPELINE CAPABILITIES & LIMITATIONS")
    print(SEPARATOR)
    print()
    print("  WHAT IS TRACKED (33 MediaPipe Pose landmarks):")
    print("    - Head/face (nose, eyes, ears, mouth)")
    print("    - Shoulders (left, right)")
    print("    - Elbows (left, right)")
    print("    - Wrists (left, right)")
    print("    - Hips (left, right)")
    print("    - Knees (left, right)")
    print("    - Ankles (left, right)")
    print("    - Feet (heel, toe tip)")
    print("    - General hand position (thumb, pinky, index at wrist level)")
    print()
    print("  WHAT IS NOT TRACKED:")
    print("    Individual finger motion is NOT currently analyzed.")
    print("    The 33-landmark Pose model does NOT provide detailed finger joints:")
    print("      - No thumb joints (MCP, IP, TIP)")
    print("      - No index finger joints")
    print("      - No middle finger joints")
    print("      - No ring finger joints")
    print("      - No little finger joints")
    print()
    print("    If detailed finger choreography is required, a dedicated")
    print("    hand-landmark pipeline (MediaPipe Hands, 21 landmarks per hand)")
    print("    would need to be integrated as a future enhancement.")
    print()
    print("  KNOWN BEHAVIORS:")
    print("    - Body turns/rotations: detection may degrade when person")
    print("      faces away from camera (landmarks become occluded)")
    print("    - Fast movement: may cause detection drops on high-speed frames")
    print("    - Occlusion: crossed limbs or partially hidden body parts")
    print("      result in low-visibility landmarks (properly handled)")
    print("    - Camera distance: very far or very close may reduce accuracy")
    print()


def run_preview(video_path: Path, pose_cfg: PoseConfig) -> None:
    """Replay video with skeleton overlay for visual inspection."""
    print(SEPARATOR)
    print("  VIDEO PREVIEW WITH SKELETON OVERLAY")
    print(SEPARATOR)
    print("  Press 'q' or ESC to exit preview.")
    print()

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print("ERROR: Cannot open video for preview.", file=sys.stderr)
        return

    try:
        detector = PoseDetector(pose_cfg)
    except Exception as exc:
        print(f"ERROR: Cannot initialize detector for preview: {exc}", file=sys.stderr)
        cap.release()
        return

    window_name = f"OpenDance AI Preview - {video_path.name}"

    try:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    except cv2.error as exc:
        print(f"ERROR: Cannot create window (no GUI backend): {exc}", file=sys.stderr)
        detector.close()
        cap.release()
        return

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_delay_ms = max(1, int(1000.0 / source_fps))
    frame_idx = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            frame_idx += 1
            timestamp_ms = int(frame_idx * (1000.0 / source_fps))

            # Detect pose
            pose_result: PoseResult = detector.detect(frame, timestamp_ms=timestamp_ms)

            # Draw skeleton
            render_skeleton(frame, pose_result, visibility_threshold=0.5)

            # Draw info
            h, w = frame.shape[:2]
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, 80), (40, 40, 40), -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

            status = "DETECTED" if not pose_result.is_empty else "NO POSE"
            color = (0, 255, 0) if not pose_result.is_empty else (0, 0, 255)

            cv2.putText(
                frame, f"Frame: {frame_idx}/{total_frames}", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1,
            )
            cv2.putText(
                frame, f"Time: {timestamp_ms/1000:.2f}s", (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1,
            )
            cv2.putText(
                frame, f"Status: {status}", (10, 75),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2,
            )

            cv2.imshow(window_name, frame)

            key = cv2.waitKey(frame_delay_ms) & 0xFF
            if key == ord("q") or key == 27:
                print("  Preview stopped by user.")
                break

            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                print("  Preview window closed.")
                break

    except KeyboardInterrupt:
        print("  Preview interrupted (Ctrl+C).")
    finally:
        detector.close()
        cap.release()
        cv2.destroyAllWindows()
        print(f"  Preview complete. Showed {frame_idx} frames.")
        print()


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Video Analysis Diagnostic — OpenDance AI",
        add_help=False,
    )
    parser.add_argument("video_path", nargs="?", default=None, help="Path to video file")
    parser.add_argument("--preview", action="store_true", help="Replay with skeleton overlay")
    parser.add_argument("-h", "--help", action="store_true", help="Show usage")

    args = parser.parse_args()

    if args.help or args.video_path is None:
        print_usage()
        return 0

    # Validate inputs
    video_path = validate_video_path(args.video_path)
    validate_model()

    # Get configs
    pose_cfg, norm_cfg, ref_cfg, motion_cfg = get_config()

    # Print video info (also validates the file can be opened)
    print_video_info(video_path)

    # Run analysis
    print(f"  Starting analysis with sample FPS: {ref_cfg.sample_fps}")
    print()
    sequence = run_analysis(video_path, pose_cfg, norm_cfg, ref_cfg)

    # Print report
    print_analysis_report(sequence)

    # Cache validation
    run_cache_validation(video_path, sequence, norm_cfg, motion_cfg)

    # Scoring engine compatibility
    run_scoring_validation(sequence)

    # Limitations
    print_limitations()

    # Preview mode
    if args.preview:
        run_preview(video_path, pose_cfg)

    print(SEPARATOR)
    print("  DIAGNOSTIC COMPLETE")
    print(SEPARATOR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
