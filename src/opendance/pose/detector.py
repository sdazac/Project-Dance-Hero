"""MediaPipe Pose Landmarker wrapper for OpenDance AI.

Initializes the model once and reuses it for all subsequent frames.
Uses VIDEO running mode for sequential frame processing.
"""

import logging
from pathlib import Path

import numpy as np

from opendance.config.models import PoseConfig
from opendance.pose.result import Landmark, PoseResult, WorldLandmark

logger = logging.getLogger(__name__)


class PoseDetector:
    """Wraps MediaPipe Pose Landmarker: one-time init, reuse for all frames.

    The detector uses VIDEO running mode for sequential frame processing.
    """

    def __init__(self, config: PoseConfig) -> None:
        """Initialize MediaPipe PoseLandmarker from the configured model path.

        Args:
            config: Pose configuration with model_path and thresholds.

        Raises:
            FileNotFoundError: If the model file does not exist at the configured path.
        """
        model_path = Path(config.model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"MediaPipe pose model not found at: {model_path.resolve()}"
            )

        # Import MediaPipe here to allow mocking in tests
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python.vision import (
            PoseLandmarker,
            PoseLandmarkerOptions,
        )
        from mediapipe.tasks.python.vision.core.vision_task_running_mode import (
            VisionTaskRunningMode,
        )

        base_options = BaseOptions(model_asset_path=str(model_path))
        options = PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=VisionTaskRunningMode.VIDEO,
            num_poses=1,
        )
        self._landmarker = PoseLandmarker.create_from_options(options)
        self._config = config
        logger.info("PoseDetector initialized with model: %s", model_path)

    def detect(self, frame: np.ndarray, timestamp_ms: int = 0) -> PoseResult:
        """Run pose detection on a BGR frame. Returns PoseResult (possibly empty).

        Never raises on detection failure — returns PoseResult.empty().

        Args:
            frame: BGR image as numpy ndarray (H, W, 3).
            timestamp_ms: Frame timestamp in milliseconds (must increase between calls).

        Returns:
            A PoseResult with landmarks, or PoseResult.empty() if no pose detected.
        """
        try:
            import cv2
            import mediapipe as mp

            # Convert BGR to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

            if not result.pose_landmarks or len(result.pose_landmarks) == 0:
                return PoseResult.empty(timestamp_ms=timestamp_ms)

            # Take first detected pose
            pose_landmarks = result.pose_landmarks[0]
            landmarks = tuple(
                Landmark(
                    x=lm.x,
                    y=lm.y,
                    z=lm.z,
                    visibility=lm.visibility if hasattr(lm, "visibility") else 0.0,
                    presence=lm.presence if hasattr(lm, "presence") else 0.0,
                )
                for lm in pose_landmarks
            )

            # World landmarks (meter-space, hip-centered)
            world_landmarks: tuple[WorldLandmark, ...] = ()
            if result.pose_world_landmarks and len(result.pose_world_landmarks) > 0:
                pose_world = result.pose_world_landmarks[0]
                world_landmarks = tuple(
                    WorldLandmark(
                        x=wl.x,
                        y=wl.y,
                        z=wl.z,
                        visibility=wl.visibility if hasattr(wl, "visibility") else 0.0,
                        presence=wl.presence if hasattr(wl, "presence") else 0.0,
                    )
                    for wl in pose_world
                )

            return PoseResult(
                landmarks=landmarks,
                world_landmarks=world_landmarks,
                timestamp_ms=timestamp_ms,
            )

        except Exception as exc:
            logger.warning("Pose detection failed on frame: %s", exc)
            return PoseResult.empty(timestamp_ms=timestamp_ms)

    def close(self) -> None:
        """Release MediaPipe resources."""
        if hasattr(self, "_landmarker") and self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception as exc:
                logger.warning("Error closing PoseLandmarker: %s", exc)
            self._landmarker = None  # type: ignore[assignment]
            logger.info("PoseDetector resources released.")
