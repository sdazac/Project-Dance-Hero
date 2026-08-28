"""Reference video analysis: extract pose, normalize, compute motion features.

Processes a local video file with deterministic FPS-based sampling.
Uses PoseDetector (Phase 1, unchanged) for per-frame detection.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from opendance.config.models import NormalizationConfig, PoseConfig, ReferenceConfig
from opendance.motion.angles import compute_joint_angles
from opendance.motion.features import compute_sequence_motion
from opendance.motion.normalized_pose import NormalizedPose
from opendance.motion.normalizer import normalize_pose
from opendance.pose.detector import PoseDetector
from opendance.pose.result import PoseResult
from opendance.video.reference_sequence import ReferenceSequence, VideoMetadata

logger = logging.getLogger(__name__)


class ReferenceAnalyzer:
    """Processes a reference video with deterministic FPS sampling.

    Sampling: frames are extracted at intervals of 1000/sample_fps ms.
    Each sample receives its authoritative timestamp_ms = sample_index * (1000/sample_fps).
    PoseDetector.detect(frame, timestamp_ms) is called with this authoritative timestamp.

    This class does NOT modify PoseDetector or its API.
    """

    def __init__(
        self,
        pose_config: PoseConfig,
        normalization_config: NormalizationConfig,
        reference_config: ReferenceConfig,
    ) -> None:
        self._pose_config = pose_config
        self._normalization_config = normalization_config
        self._reference_config = reference_config
        self._pose_detector: PoseDetector | None = None

    def analyze(
        self,
        video_path: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> ReferenceSequence:
        """Analyze video. Accepts local filesystem path only.

        Steps:
        1. Validate path exists locally.
        2. Open with cv2.VideoCapture(video_path).
        3. Extract metadata (fps, frame_count, duration, resolution).
        4. Compute sample timestamps at configured sample_fps.
        5. For each sample: seek/read frame → detect → normalize → angles.
        6. Compute motion features via central differences on full sequence.
        7. Assemble ReferenceSequence.

        Raises:
            FileNotFoundError: If video_path does not exist.
            ValueError: If video cannot be opened.
        """
        import cv2

        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        try:
            return self._process_video(capture, video_path, progress_callback)
        finally:
            capture.release()

    def _process_video(
        self,
        capture: Any,
        video_path: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> ReferenceSequence:
        """Internal: process opened VideoCapture."""
        import cv2

        # Extract metadata
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / video_fps if video_fps > 0 else 0.0

        metadata = VideoMetadata(
            file_path=video_path,
            total_frames=total_frames,
            fps=video_fps,
            duration_seconds=duration,
            width=width,
            height=height,
        )

        # Initialize PoseDetector
        if self._pose_detector is None:
            self._pose_detector = PoseDetector(self._pose_config)

        sample_fps = self._reference_config.sample_fps
        sample_interval_ms = 1000.0 / sample_fps

        # Compute number of samples
        duration_ms = duration * 1000.0
        num_samples = int(duration_ms / sample_interval_ms) if sample_interval_ms > 0 else 0

        logger.info(
            "Analyzing video: %s (%d frames, %.1f fps, %d samples at %.1f sample_fps)",
            video_path,
            total_frames,
            video_fps,
            num_samples,
            sample_fps,
        )

        # Initialize the progress bar even when there is nothing to process,
        # so the UI can render a bar for empty/undecodable videos.
        if num_samples == 0 and progress_callback is not None:
            progress_callback(0, 0)

        # Process each sample
        poses: list[NormalizedPose | None] = []
        angles_list: list[dict[str, float | None] | None] = []

        for sample_idx in range(num_samples):
            # The per-sample work is delegated so this loop body has no early
            # exits; progress is therefore reported exactly once per iteration,
            # including samples whose frame/pose is skipped.
            self._process_sample(
                capture, sample_idx, sample_interval_ms, video_fps, poses, angles_list
            )
            if progress_callback is not None:
                progress_callback(sample_idx + 1, num_samples)

        # Compute motion features from the full sequence
        from opendance.config.models import MotionConfig

        motion_results = compute_sequence_motion(poses, config=MotionConfig())

        return ReferenceSequence(
            metadata=metadata,
            poses=tuple(poses),
            motion_features=tuple(motion_results),
            joint_angles=tuple(angles_list),
        )

    def _process_sample(
        self,
        capture: Any,
        sample_idx: int,
        sample_interval_ms: float,
        video_fps: float,
        poses: list[NormalizedPose | None],
        angles_list: list[dict[str, float | None] | None],
    ) -> None:
        """Process a single sample, appending its pose/angles to the sequences.

        Always appends exactly one entry to each of ``poses`` and
        ``angles_list`` (``None`` when the frame or pose is unusable), so the
        caller can report progress once per sample regardless of the outcome.
        """
        import cv2

        assert self._pose_detector is not None

        timestamp_ms = int(sample_idx * sample_interval_ms)

        # Seek to the corresponding video frame
        frame_number = int((timestamp_ms / 1000.0) * video_fps)
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        ok, frame = capture.read()
        if not ok or frame is None:
            poses.append(None)
            angles_list.append(None)
            return

        # Detect pose
        pose_result: PoseResult = self._pose_detector.detect(frame, timestamp_ms)

        if pose_result.is_empty:
            poses.append(None)
            angles_list.append(None)
            return

        # Normalize
        normalized = normalize_pose(pose_result, self._normalization_config)
        poses.append(normalized if normalized.valid else None)

        # Joint angles
        if normalized.valid:
            angles = compute_joint_angles(normalized)
            angles_list.append(angles)
        else:
            angles_list.append(None)

    def close(self) -> None:
        """Release PoseDetector resources."""
        if self._pose_detector is not None:
            self._pose_detector.close()
            self._pose_detector = None
            logger.info("ReferenceAnalyzer PoseDetector released.")
