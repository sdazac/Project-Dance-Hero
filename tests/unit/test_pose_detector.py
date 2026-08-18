"""Unit tests for PoseDetector with mocked MediaPipe.

Property 6: Pose detection produces valid result for any frame without exception.
Tests use mocked MediaPipe — no model file or GPU required.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from opendance.config.models import PoseConfig
from opendance.pose.detector import PoseDetector
from opendance.pose.result import PoseResult


class TestPoseDetectorInit:
    """Test PoseDetector initialization behavior."""

    def test_raises_file_not_found_if_model_missing(self) -> None:
        """FileNotFoundError when model path doesn't exist."""
        config = PoseConfig(model_path="nonexistent/model.task")
        with pytest.raises(FileNotFoundError, match="not found"):
            PoseDetector(config)


class TestPoseDetectorDetect:
    """Test PoseDetector.detect() behavior with mocked internals."""

    def _make_detector(self, mock_landmarker: MagicMock) -> PoseDetector:
        """Create a PoseDetector with a pre-set mock landmarker (bypasses __init__)."""
        config = PoseConfig(model_path="dummy.task")
        detector = object.__new__(PoseDetector)
        detector._landmarker = mock_landmarker  # type: ignore[attr-defined]
        detector._config = config  # type: ignore[attr-defined]
        return detector

    def test_returns_empty_when_no_pose_detected(self) -> None:
        """detect() returns PoseResult.empty() when MediaPipe finds no pose."""
        mock_landmarker = MagicMock()
        mock_result = MagicMock()
        mock_result.pose_landmarks = []
        mock_result.pose_world_landmarks = []
        mock_landmarker.detect_for_video.return_value = mock_result

        detector = self._make_detector(mock_landmarker)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame, timestamp_ms=100)

        assert result.is_empty
        assert result.timestamp_ms == 100

    def test_returns_landmarks_when_pose_detected(self) -> None:
        """detect() returns populated PoseResult when MediaPipe detects a pose."""
        mock_landmarker = MagicMock()
        mock_landmarks = []
        for i in range(33):
            lm = MagicMock()
            lm.x = float(i) / 33.0
            lm.y = float(i) / 33.0
            lm.z = 0.0
            lm.visibility = 0.9
            lm.presence = 0.95
            mock_landmarks.append(lm)

        mock_world_landmarks = []
        for i in range(33):
            wl = MagicMock()
            wl.x = float(i) * 0.01
            wl.y = float(i) * 0.01
            wl.z = 0.0
            wl.visibility = 0.9
            wl.presence = 0.95
            mock_world_landmarks.append(wl)

        mock_result = MagicMock()
        mock_result.pose_landmarks = [mock_landmarks]
        mock_result.pose_world_landmarks = [mock_world_landmarks]
        mock_landmarker.detect_for_video.return_value = mock_result

        detector = self._make_detector(mock_landmarker)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame, timestamp_ms=200)

        assert not result.is_empty
        assert len(result.landmarks) == 33
        assert len(result.world_landmarks) == 33
        assert result.timestamp_ms == 200
        assert result.landmarks[0].visibility == 0.9
        assert result.world_landmarks[0].x == 0.0

    def test_returns_empty_on_exception(self) -> None:
        """detect() returns PoseResult.empty() when MediaPipe raises."""
        mock_landmarker = MagicMock()
        mock_landmarker.detect_for_video.side_effect = RuntimeError("inference error")

        detector = self._make_detector(mock_landmarker)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame, timestamp_ms=300)

        assert result.is_empty
        assert result.timestamp_ms == 300

    def test_handles_various_frame_sizes(self) -> None:
        """detect() works with various frame dimensions without crashing."""
        mock_landmarker = MagicMock()
        mock_result = MagicMock()
        mock_result.pose_landmarks = []
        mock_result.pose_world_landmarks = []
        mock_landmarker.detect_for_video.return_value = mock_result

        detector = self._make_detector(mock_landmarker)

        for h, w in [(1, 1), (100, 200), (1080, 1920)]:
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            result = detector.detect(frame, timestamp_ms=0)
            assert isinstance(result, PoseResult)


class TestPoseDetectorClose:
    """Test PoseDetector resource cleanup."""

    def test_close_releases_landmarker(self) -> None:
        """close() calls landmarker.close()."""
        mock_landmarker = MagicMock()
        config = PoseConfig(model_path="dummy.task")
        detector = object.__new__(PoseDetector)
        detector._landmarker = mock_landmarker  # type: ignore[attr-defined]
        detector._config = config  # type: ignore[attr-defined]

        detector.close()
        mock_landmarker.close.assert_called_once()

    def test_close_handles_exception_gracefully(self) -> None:
        """close() doesn't raise if landmarker.close() fails."""
        mock_landmarker = MagicMock()
        mock_landmarker.close.side_effect = RuntimeError("close failed")
        config = PoseConfig(model_path="dummy.task")
        detector = object.__new__(PoseDetector)
        detector._landmarker = mock_landmarker  # type: ignore[attr-defined]
        detector._config = config  # type: ignore[attr-defined]

        # Should not raise
        detector.close()
