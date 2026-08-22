"""Performance, Temporal Fidelity & Multi-Person Diagnostic.

Benchmarks the reference analysis pipeline at different sample FPS rates
and investigates multi-person and temporal synchronization concerns.

Usage:
    python scripts/performance_diagnostic.py path/to/video.mp4
"""

import argparse
import sys
import time
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "src"))

import cv2  # noqa: E402

from opendance.config.models import (  # noqa: E402
    NormalizationConfig,
    PoseConfig,
    ReferenceConfig,
)
from opendance.video.reference_analyzer import ReferenceAnalyzer  # noqa: E402
from opendance.video.reference_sequence import ReferenceSequence  # noqa: E402

# --- Constants ---

MODEL_PATH = str(_project_root / "assets" / "models" / "pose_landmarker.task")
BENCHMARK_FPS_RATES: list[float] = [10.0, 15.0, 20.0, 30.0]
ESTIMATED_BYTES_PER_FRAME = 3000  # ~3 KB per frame (pose + motion + angles)
SEPARATOR = "=" * 80
THIN_SEP = "-" * 80


def get_video_info(video_path: str) -> dict[str, float | int]:
    """Extract basic video metadata without full analysis."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0.0
        return {
            "total_frames": total_frames,
            "fps": fps,
            "width": width,
            "height": height,
            "duration": duration,
        }
    finally:
        cap.release()


def estimate_memory_bytes(num_frames: int) -> int:
    """Estimate memory usage of ReferenceSequence in bytes."""
    return num_frames * ESTIMATED_BYTES_PER_FRAME


def format_bytes(num_bytes: int) -> str:
    """Format bytes as human-readable string."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    else:
        return f"{num_bytes / (1024 * 1024):.2f} MB"


def run_benchmark(
    video_path: str,
    sample_fps: float,
    pose_config: PoseConfig,
    norm_config: NormalizationConfig,
) -> dict[str, object]:
    """Run a single benchmark at the given sample FPS.

    Returns dict with timing and result metrics.
    """
    ref_config = ReferenceConfig(sample_fps=sample_fps)
    analyzer = ReferenceAnalyzer(
        pose_config=pose_config,
        normalization_config=norm_config,
        reference_config=ref_config,
    )

    start = time.perf_counter()
    try:
        sequence: ReferenceSequence = analyzer.analyze(video_path)
    finally:
        analyzer.close()
    elapsed = time.perf_counter() - start

    num_frames = len(sequence.poses)
    detected = sum(1 for p in sequence.poses if p is not None)
    duration = sequence.metadata.duration_seconds
    processing_ratio = elapsed / duration if duration > 0 else 0.0
    effective_fps = num_frames / elapsed if elapsed > 0 else 0.0
    avg_ms_per_frame = (elapsed * 1000.0) / num_frames if num_frames > 0 else 0.0
    memory_est = estimate_memory_bytes(num_frames)

    return {
        "sample_fps": sample_fps,
        "source_fps": sequence.metadata.fps,
        "total_source_frames": sequence.metadata.total_frames,
        "frames_analyzed": num_frames,
        "frames_detected": detected,
        "detection_rate": detected / num_frames if num_frames > 0 else 0.0,
        "video_duration": duration,
        "wall_time": elapsed,
        "processing_ratio": processing_ratio,
        "effective_fps": effective_fps,
        "avg_ms_per_frame": avg_ms_per_frame,
        "memory_bytes": memory_est,
        "width": sequence.metadata.width,
        "height": sequence.metadata.height,
    }


def print_video_info(info: dict[str, float | int]) -> None:
    """Print video metadata summary."""
    print(SEPARATOR)
    print("  VIDEO INFORMATION")
    print(SEPARATOR)
    print(f"  Resolution:     {info['width']}x{info['height']}")
    print(f"  Source FPS:     {info['fps']:.2f}")
    print(f"  Total frames:   {info['total_frames']}")
    print(f"  Duration:       {info['duration']:.2f}s")
    print()


def print_benchmark_result(result: dict[str, object], index: int) -> None:
    """Print a single benchmark result."""
    print(THIN_SEP)
    print(f"  Benchmark {index}: Analysis FPS = {result['sample_fps']}")
    print(THIN_SEP)
    print(f"  Source FPS:           {result['source_fps']}")
    print(f"  Frames analyzed:      {result['frames_analyzed']}")
    print(f"  Frames detected:      {result['frames_detected']}")
    det_rate = float(str(result["detection_rate"])) * 100
    print(f"  Detection rate:       {det_rate:.1f}%")
    print(f"  Video duration:       {result['video_duration']:.2f}s")
    print(f"  Wall-clock time:      {result['wall_time']:.2f}s")
    ratio = float(str(result["processing_ratio"]))
    speed = "slower" if ratio > 1.0 else "faster"
    print(
        f"  Processing ratio:     {ratio:.2f}x ({speed}"
        f" than real-time)"
    )
    print(f"  Effective FPS:        {result['effective_fps']:.2f}")
    print(f"  Avg time/frame:       {result['avg_ms_per_frame']:.1f} ms")
    mem_bytes = int(str(result["memory_bytes"]))
    print(f"  Est. memory:          {format_bytes(mem_bytes)}")
    print()


def print_summary_table(results: list[dict[str, object]]) -> None:
    """Print comparison table of all benchmark results."""
    print(SEPARATOR)
    print("  BENCHMARK SUMMARY TABLE")
    print(SEPARATOR)
    header = (
        f"  {'FPS':>4} | {'Frames':>6} | {'Wall(s)':>8} | "
        f"{'Ratio':>6} | {'Eff.FPS':>7} | {'ms/frm':>7} | {'Memory':>8}"
    )
    print(header)
    print(f"  {'-' * 4}-+-{'-' * 6}-+-{'-' * 8}-+-"
          f"{'-' * 6}-+-{'-' * 7}-+-{'-' * 7}-+-{'-' * 8}")
    for r in results:
        wall = float(str(r["wall_time"]))
        ratio = float(str(r["processing_ratio"]))
        eff = float(str(r["effective_fps"]))
        avg_ms = float(str(r["avg_ms_per_frame"]))
        mem = int(str(r["memory_bytes"]))
        row = (
            f"  {r['sample_fps']:>4.0f} | "
            f"{r['frames_analyzed']:>6} | "
            f"{wall:>8.2f} | "
            f"{ratio:>5.2f}x | "
            f"{eff:>7.2f} | "
            f"{avg_ms:>7.1f} | "
            f"{format_bytes(mem):>8}"
        )
        print(row)
    print()


def print_multi_person_analysis() -> None:
    """Print multi-person detection behavior analysis."""
    print(SEPARATOR)
    print("  MULTI-PERSON DETECTION ANALYSIS")
    print(SEPARATOR)
    print()
    print("  Current PoseDetector configuration:")
    print("    num_poses = 1  (hardcoded in PoseDetector.__init__)")
    print()
    print("  Behavior:")
    print("    - MediaPipe returns only the FIRST detected pose")
    print("    - No selection logic for which person is returned")
    print("    - MediaPipe internally selects 'most prominent' pose")
    print("    - Priority is undefined and may vary between frames")
    print()
    print("  Impact on multi-person videos:")
    print("    - Detected person may switch between dancers")
    print("    - Frame-to-frame jumps cause discontinuities")
    print("    - Motion features become unreliable at switch points")
    print("    - Normalization may produce erratic body_scale changes")
    print()
    print("  >>> CURRENT PIPELINE: SINGLE-PERSON ONLY <<<")
    print()
    print("  Recommendation for multi-person support (Phase 4):")
    print("    1. Increase num_poses to 3-5")
    print("    2. Score each detected pose by bounding box area")
    print("    3. Select largest (most visible) person")
    print("    4. Apply hysteresis to avoid frame-to-frame switching")
    print()


def print_temporal_fidelity_analysis() -> None:
    """Print temporal fidelity and synchronization analysis."""
    print(SEPARATOR)
    print("  TEMPORAL FIDELITY ANALYSIS")
    print(SEPARATOR)
    print()
    print("  Timestamp authority in ReferenceAnalyzer:")
    print("    timestamp_ms = sample_index * (1000 / sample_fps)")
    print("    This is AUTHORITATIVE — it defines real video time.")
    print()
    print("  Frame selection:")
    print("    frame_number = int((timestamp_ms / 1000.0) * video_fps)")
    print("    Maps authoritative timestamp to nearest source frame.")
    print()
    print("  Key architectural principle:")
    print("    - Analysis is OFFLINE")
    print("    - Wall-clock processing time is IRRELEVANT to timestamps")
    print("    - Whether analysis takes 10s or 10min, timestamps are same")
    print("    - Timestamps correctly represent original video time")
    print()
    print("  Known desync issue in diagnostic scripts:")
    print("    landmark_replay.py uses: sample_interval_ms = 1000/30.0")
    print("    This is WRONG if source FPS != 30.")
    print("    Fix: use sequence.metadata.fps for replay timing.")
    print()
    print("  Correct replay timing:")
    print("    interval_ms = 1000.0 / sequence.metadata.fps")
    print("    NOT 1000.0 / sample_fps")
    print()
    print("  Scoring comparison:")
    print("    Uses timestamp_ms for temporal alignment — CORRECT")
    print("    Independent of analysis FPS or wall-clock time.")
    print()


def print_recommendation(results: list[dict[str, object]]) -> None:
    """Print final FPS recommendation based on results."""
    print(SEPARATOR)
    print("  RECOMMENDATION")
    print(SEPARATOR)
    print()
    print("  Analysis FPS selection guide:")
    print()
    print(
        f"  {'FPS':>4} | {'Temporal Res':>12} | "
        f"{'Use Case':>30}"
    )
    print(f"  {'-' * 4}-+-{'-' * 12}-+-{'-' * 30}")
    print(f"  {'10':>4} | {'100 ms':>12} | "
          f"{'Quick preview / slow choreography':>30}")
    print(f"  {'15':>4} | {'66 ms':>12} | "
          f"{'Default — good balance':>30}")
    print(f"  {'20':>4} | {'50 ms':>12} | "
          f"{'Fast choreography':>30}")
    print(f"  {'30':>4} | {'33 ms':>12} | "
          f"{'Competition / maximum fidelity':>30}")
    print()

    # Find the result closest to real-time
    best: dict[str, object] | None = None
    for r in results:
        ratio = float(str(r["processing_ratio"]))
        if ratio <= 1.0:
            if best is None or float(
                str(best["processing_ratio"])
            ) < ratio:
                best = r

    if best is not None:
        best_ratio = float(str(best["processing_ratio"]))
        print(
            f"  Highest FPS at/below real-time: "
            f"{best['sample_fps']} FPS "
            f"(ratio {best_ratio:.2f}x)"
        )
    else:
        print("  All tested rates exceed real-time processing.")
        print("  Consider GPU acceleration or lower analysis FPS.")

    print()
    print("  Default recommendation: 15 FPS")
    print("    - 66ms temporal resolution (sufficient for dance)")
    print("    - Approaches real-time on CPU")
    print("    - Good scoring accuracy")
    print("    - Manageable memory footprint")
    print()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Performance, Temporal Fidelity & Multi-Person Diagnostic "
            "for OpenDance AI reference analysis pipeline."
        ),
    )
    parser.add_argument(
        "video",
        type=str,
        help="Path to a video file to benchmark.",
    )
    parser.add_argument(
        "--fps",
        type=float,
        nargs="*",
        default=None,
        help=(
            "Custom FPS rates to benchmark "
            "(default: 10, 15, 20, 30)."
        ),
    )
    parser.add_argument(
        "--model",
        type=str,
        default=MODEL_PATH,
        help="Path to pose_landmarker.task model file.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the performance diagnostic."""
    args = parse_args()

    video_path = args.video
    fps_rates = args.fps if args.fps else BENCHMARK_FPS_RATES
    model_path = args.model

    # Validate inputs
    if not Path(video_path).exists():
        print(f"ERROR: Video file not found: {video_path}", file=sys.stderr)
        return 1

    if not Path(model_path).exists():
        print(
            f"ERROR: Model file not found: {model_path}\n"
            "Run: python scripts/download_models.py",
            file=sys.stderr,
        )
        return 1

    # Get video info
    print()
    try:
        info = get_video_info(video_path)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print_video_info(info)

    # Prepare configs
    pose_config = PoseConfig(model_path=model_path)
    norm_config = NormalizationConfig(enabled=True)

    # Run benchmarks
    print(SEPARATOR)
    print("  RUNNING BENCHMARKS")
    print(SEPARATOR)
    print()

    results: list[dict[str, object]] = []
    for i, fps in enumerate(fps_rates, start=1):
        print(f"  [{i}/{len(fps_rates)}] Benchmarking at {fps} FPS...")
        try:
            result = run_benchmark(
                video_path, fps, pose_config, norm_config
            )
            results.append(result)
            print_benchmark_result(result, i)
        except Exception as exc:
            print(
                f"  ERROR during benchmark at {fps} FPS: {exc}",
                file=sys.stderr,
            )
            print()

    if not results:
        print("ERROR: All benchmarks failed.", file=sys.stderr)
        return 1

    # Summary
    print_summary_table(results)
    print_multi_person_analysis()
    print_temporal_fidelity_analysis()
    print_recommendation(results)

    print(SEPARATOR)
    print("  DIAGNOSTIC COMPLETE")
    print(SEPARATOR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
