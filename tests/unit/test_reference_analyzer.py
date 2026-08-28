"""Unit tests for ReferenceAnalyzer with mocked VideoCapture and PoseDetector.

Tests:
- Synthetic 5-frame mock video
- No-detection frames → None entries
- Metadata extraction
- Deterministic timestamp assignment
- FileNotFoundError for missing video
- ValueError for unopenable video
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from opendance.config.models import NormalizationConfig, PoseConfig, ReferenceConfig
from opendance.pose.result import Landmark, PoseResult
from opendance.video.reference_analyzer import ReferenceAnalyzer


def _make_landmark(
    x: float = 0.5, y: float = 0.5, z: float = 0.0,
    visibility: float = 1.0, presence: float = 1.0,
) -> Landmark:
    return Landmark(x=x, y=y, z=z, visibility=visibility, presence=presence)


def _make_valid_pose_result(timestamp_ms: int = 0) -> PoseResult:
    """Create a PoseResult with body landmarks placed for successful normalization."""
    from opendance.motion.landmarks import LEFT_HIP, LEFT_SHOULDER, NUM_LANDMARKS, RIGHT_HIP

    landmarks = [_make_landmark(0.5, 0.5, 0.0, 1.0)] * NUM_LANDMARKS
    lm_list = list(landmarks)
    lm_list[LEFT_HIP] = _make_landmark(0.4, 0.6, 0.0, 1.0)
    lm_list[RIGHT_HIP] = _make_landmark(0.6, 0.6, 0.0, 1.0)
    lm_list[LEFT_SHOULDER] = _make_landmark(0.4, 0.3, 0.0, 1.0)
    return PoseResult(landmarks=tuple(lm_list), world_landmarks=(), timestamp_ms=timestamp_ms)


@pytest.fixture()
def pose_config(tmp_path: Path) -> PoseConfig:
    model = tmp_path / "model.task"
    model.write_bytes(b"fake")
    return PoseConfig(model_path=str(model))


@pytest.fixture()
def norm_config() -> NormalizationConfig:
    return NormalizationConfig(enabled=True)


@pytest.fixture()
def ref_config() -> ReferenceConfig:
    return ReferenceConfig(sample_fps=30.0)


class TestReferenceAnalyzerFileErrors:
    """Test error handling for invalid video paths."""

    def test_file_not_found(
        self, pose_config: PoseConfig, norm_config: NormalizationConfig, ref_config: ReferenceConfig
    ) -> None:
        analyzer = ReferenceAnalyzer(pose_config, norm_config, ref_config)
        with pytest.raises(FileNotFoundError):
            analyzer.analyze("/nonexistent/video.mp4")

    def test_cannot_open_video(
        self,
        tmp_path: Path,
        pose_config: PoseConfig,
        norm_config: NormalizationConfig,
        ref_config: ReferenceConfig,
    ) -> None:
        video_file = tmp_path / "bad.mp4"
        video_file.write_bytes(b"not a video")

        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = False

        with patch("cv2.VideoCapture", return_value=mock_capture):
            analyzer = ReferenceAnalyzer(pose_config, norm_config, ref_config)
            with pytest.raises(ValueError, match="Cannot open"):
                analyzer.analyze(str(video_file))


class TestReferenceAnalyzerProcessing:
    """Test video processing with mocked capture and PoseDetector."""

    def _setup_mock_capture(self, num_frames: int = 5, fps: float = 30.0) -> MagicMock:
        """Create a mock VideoCapture that returns synthetic frames."""
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = True
        # cv2 constants: FRAME_COUNT=7, FPS=5, WIDTH=3, HEIGHT=4
        mock_capture.get.side_effect = lambda prop: {
            7: float(num_frames),   # CAP_PROP_FRAME_COUNT
            5: fps,                  # CAP_PROP_FPS
            3: 640.0,               # CAP_PROP_FRAME_WIDTH
            4: 480.0,               # CAP_PROP_FRAME_HEIGHT
        }.get(prop, 0.0)

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_capture.read.return_value = (True, fake_frame)
        mock_capture.set.return_value = True
        return mock_capture

    def test_five_frame_video_produces_sequence(
        self,
        tmp_path: Path,
        pose_config: PoseConfig,
        norm_config: NormalizationConfig,
        ref_config: ReferenceConfig,
    ) -> None:
        """5-frame video with all poses detected → 5 valid entries."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video data")

        mock_capture = self._setup_mock_capture(num_frames=5, fps=30.0)
        valid_pose = _make_valid_pose_result()

        with patch("cv2.VideoCapture", return_value=mock_capture), \
             patch(
                 "opendance.video.reference_analyzer.PoseDetector"
             ) as mock_pd_class:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = valid_pose
            mock_pd_class.return_value = mock_detector

            analyzer = ReferenceAnalyzer(pose_config, norm_config, ref_config)
            seq = analyzer.analyze(str(video_file))

        assert seq.metadata.file_path == str(video_file)
        assert seq.metadata.fps == 30.0
        assert seq.metadata.width == 640
        assert seq.metadata.height == 480
        assert len(seq.poses) > 0
        assert len(seq.motion_features) == len(seq.poses)
        assert len(seq.joint_angles) == len(seq.poses)

    def test_no_detection_produces_none_entries(
        self,
        tmp_path: Path,
        pose_config: PoseConfig,
        norm_config: NormalizationConfig,
        ref_config: ReferenceConfig,
    ) -> None:
        """Frames with no pose detection produce None in sequence."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake")

        mock_capture = self._setup_mock_capture(num_frames=5, fps=30.0)
        empty_pose = PoseResult.empty(timestamp_ms=0)

        with patch("cv2.VideoCapture", return_value=mock_capture), \
             patch(
                 "opendance.video.reference_analyzer.PoseDetector"
             ) as mock_pd_class:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = empty_pose
            mock_pd_class.return_value = mock_detector

            analyzer = ReferenceAnalyzer(pose_config, norm_config, ref_config)
            seq = analyzer.analyze(str(video_file))

        # All poses should be None (empty detection)
        assert all(p is None for p in seq.poses)
        assert all(a is None for a in seq.joint_angles)

    def test_deterministic_timestamp_assignment(
        self,
        tmp_path: Path,
        pose_config: PoseConfig,
        norm_config: NormalizationConfig,
    ) -> None:
        """Timestamps are assigned as sample_index * (1000/sample_fps)."""
        ref_config = ReferenceConfig(sample_fps=10.0)  # 100ms intervals
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake")

        mock_capture = self._setup_mock_capture(num_frames=30, fps=30.0)

        timestamps_received: list[int] = []

        def mock_detect(frame: object, timestamp_ms: int = 0) -> PoseResult:
            timestamps_received.append(timestamp_ms)
            return _make_valid_pose_result(timestamp_ms)

        with patch("cv2.VideoCapture", return_value=mock_capture), \
             patch(
                 "opendance.video.reference_analyzer.PoseDetector"
             ) as mock_pd_class:
            mock_detector = MagicMock()
            mock_detector.detect.side_effect = mock_detect
            mock_pd_class.return_value = mock_detector

            analyzer = ReferenceAnalyzer(pose_config, norm_config, ref_config)
            analyzer.analyze(str(video_file))

        # Verify deterministic timestamps: 0, 100, 200, ..., 900
        expected = [i * 100 for i in range(10)]
        assert timestamps_received == expected

    def test_metadata_extraction(
        self,
        tmp_path: Path,
        pose_config: PoseConfig,
        norm_config: NormalizationConfig,
        ref_config: ReferenceConfig,
    ) -> None:
        """Video metadata is correctly extracted."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake")

        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = True
        mock_capture.get.side_effect = lambda prop: {
            7: 150.0,   # CAP_PROP_FRAME_COUNT
            5: 25.0,    # CAP_PROP_FPS
            3: 1920.0,  # CAP_PROP_FRAME_WIDTH
            4: 1080.0,  # CAP_PROP_FRAME_HEIGHT
        }.get(prop, 0.0)
        mock_capture.read.return_value = (True, np.zeros((1080, 1920, 3), dtype=np.uint8))
        mock_capture.set.return_value = True

        with patch("cv2.VideoCapture", return_value=mock_capture), \
             patch(
                 "opendance.video.reference_analyzer.PoseDetector"
             ) as mock_pd_class:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = PoseResult.empty()
            mock_pd_class.return_value = mock_detector

            analyzer = ReferenceAnalyzer(pose_config, norm_config, ref_config)
            seq = analyzer.analyze(str(video_file))

        assert seq.metadata.total_frames == 150
        assert seq.metadata.fps == 25.0
        assert seq.metadata.width == 1920
        assert seq.metadata.height == 1080
        assert seq.metadata.duration_seconds == pytest.approx(6.0)


class TestReferenceAnalyzerCleanup:
    """Test resource cleanup."""

    def test_close_releases_detector(
        self, pose_config: PoseConfig, norm_config: NormalizationConfig, ref_config: ReferenceConfig
    ) -> None:
        analyzer = ReferenceAnalyzer(pose_config, norm_config, ref_config)
        mock_detector = MagicMock()
        analyzer._pose_detector = mock_detector
        analyzer.close()
        mock_detector.close.assert_called_once()
        assert analyzer._pose_detector is None


class TestAnalyzerProgress:
    """Test the additive progress_callback in ReferenceAnalyzer.analyze.

    Validates: Requirements 5.1, 5.2
    """

    def _setup_mock_capture(self, num_frames: int, fps: float = 30.0) -> MagicMock:
        """Create a mock VideoCapture that returns synthetic frames.

        Mirrors TestReferenceAnalyzerProcessing._setup_mock_capture so progress
        tests use the same capture-mocking conventions.
        """
        mock_capture = MagicMock()
        mock_capture.isOpened.return_value = True
        # cv2 constants: FRAME_COUNT=7, FPS=5, WIDTH=3, HEIGHT=4
        mock_capture.get.side_effect = lambda prop: {
            7: float(num_frames),   # CAP_PROP_FRAME_COUNT
            5: fps,                  # CAP_PROP_FPS
            3: 640.0,               # CAP_PROP_FRAME_WIDTH
            4: 480.0,               # CAP_PROP_FRAME_HEIGHT
        }.get(prop, 0.0)

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_capture.read.return_value = (True, fake_frame)
        mock_capture.set.return_value = True
        return mock_capture

    def test_callback_invoked_once_per_sample(
        self,
        tmp_path: Path,
        pose_config: PoseConfig,
        norm_config: NormalizationConfig,
    ) -> None:
        """Callback fires once per sample, non-decreasing, ending at (N, N)."""
        # sample_fps=10, 30 frames @ 30 fps → duration 1.0s → N = 1000ms / 100ms = 10.
        ref_config = ReferenceConfig(sample_fps=10.0)
        expected_n = 10

        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake")

        mock_capture = self._setup_mock_capture(num_frames=30, fps=30.0)
        valid_pose = _make_valid_pose_result()

        calls: list[tuple[int, int]] = []

        with patch("cv2.VideoCapture", return_value=mock_capture), \
             patch(
                 "opendance.video.reference_analyzer.PoseDetector"
             ) as mock_pd_class:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = valid_pose
            mock_pd_class.return_value = mock_detector

            analyzer = ReferenceAnalyzer(pose_config, norm_config, ref_config)
            analyzer.analyze(str(video_file), progress_callback=lambda d, t: calls.append((d, t)))

        # One call per sample.
        assert len(calls) == expected_n
        # done values are non-decreasing and end at N.
        done_values = [d for d, _ in calls]
        assert done_values == sorted(done_values)
        assert done_values[-1] == expected_n
        # Final call is (N, N).
        assert calls[-1] == (expected_n, expected_n)
        # Every call reports total == N.
        assert all(t == expected_n for _, t in calls)

    def test_no_callback_is_backward_compatible(
        self,
        tmp_path: Path,
        pose_config: PoseConfig,
        norm_config: NormalizationConfig,
    ) -> None:
        """analyze(path) without a callback returns the same sequence as before.

        Mirrors TestReferenceAnalyzerProcessing.test_five_frame_video_produces_sequence
        setup and asserts the no-callback path still works unchanged.
        """
        ref_config = ReferenceConfig(sample_fps=10.0)
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video data")

        mock_capture = self._setup_mock_capture(num_frames=30, fps=30.0)
        valid_pose = _make_valid_pose_result()

        with patch("cv2.VideoCapture", return_value=mock_capture), \
             patch(
                 "opendance.video.reference_analyzer.PoseDetector"
             ) as mock_pd_class:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = valid_pose
            mock_pd_class.return_value = mock_detector

            analyzer = ReferenceAnalyzer(pose_config, norm_config, ref_config)
            seq = analyzer.analyze(str(video_file))

        # 10 samples, all valid; behavior unchanged (no exception, expected length).
        assert len(seq.poses) == 10
        assert len(seq.motion_features) == len(seq.poses)
        assert len(seq.joint_angles) == len(seq.poses)
        assert all(p is not None for p in seq.poses)

    def test_empty_video_calls_callback_once_with_zero(
        self,
        tmp_path: Path,
        pose_config: PoseConfig,
        norm_config: NormalizationConfig,
        ref_config: ReferenceConfig,
    ) -> None:
        """num_samples == 0 → callback called exactly once with (0, 0)."""
        video_file = tmp_path / "empty.mp4"
        video_file.write_bytes(b"fake")

        # 0 frames → duration 0 → num_samples == 0.
        mock_capture = self._setup_mock_capture(num_frames=0, fps=30.0)

        calls: list[tuple[int, int]] = []

        with patch("cv2.VideoCapture", return_value=mock_capture), \
             patch(
                 "opendance.video.reference_analyzer.PoseDetector"
             ) as mock_pd_class:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = PoseResult.empty()
            mock_pd_class.return_value = mock_detector

            analyzer = ReferenceAnalyzer(pose_config, norm_config, ref_config)
            analyzer.analyze(str(video_file), progress_callback=lambda d, t: calls.append((d, t)))

        assert calls == [(0, 0)]
