"""Unit tests for AnalysisCache.

Tests:
- Round-trip write/read produces equivalent ReferenceSequence
- Cache miss returns None
- Invalidation on video mtime change
- Invalidation on config hash change
- Invalidation on model file mtime change
- Corrupted cache file → discard and return None
- Disabled cache (no directory) → always None
- No pickle used
"""

import gzip
import json
import time
from pathlib import Path

import numpy as np
import pytest

from opendance.motion.landmarks import NUM_LANDMARKS
from opendance.motion.motion_result import MotionFeatures
from opendance.motion.normalized_pose import NormalizedPose
from opendance.video.analysis_cache import AnalysisCache, compute_config_hash
from opendance.video.reference_sequence import ReferenceSequence, VideoMetadata


def _make_test_sequence(num_frames: int = 3) -> ReferenceSequence:
    """Create a minimal ReferenceSequence for cache testing."""
    poses: list[NormalizedPose | None] = []
    angles: list[dict[str, float | None] | None] = []
    for i in range(num_frames):
        lm2d = tuple(
            (float(i) * 0.1 + j * 0.01, float(j) * 0.02, 0.0)
            for j in range(NUM_LANDMARKS)
        )
        pose = NormalizedPose(
            timestamp_ms=i * 33,
            landmarks_2d=lm2d,
            landmarks_3d=None,
            visibilities=tuple(0.9 for _ in range(NUM_LANDMARKS)),
            presences=tuple(0.95 for _ in range(NUM_LANDMARKS)),
            body_center=(0.5, 0.6, 0.0),
            body_scale=0.35,
            valid=True,
        )
        poses.append(pose)
        angles.append({"left_elbow": 90.0 + i, "right_elbow": None})

    # Simple motion features
    motion: list[MotionFeatures | None] = [None] * num_frames

    return ReferenceSequence(
        metadata=VideoMetadata(
            file_path="/test/video.mp4",
            total_frames=90,
            fps=30.0,
            duration_seconds=3.0,
            width=640,
            height=480,
        ),
        poses=tuple(poses),
        motion_features=tuple(motion),
        joint_angles=tuple(angles),
    )


@pytest.fixture()
def video_file(tmp_path: Path) -> Path:
    """Create a fake video file."""
    vf = tmp_path / "video.mp4"
    vf.write_bytes(b"fake video content")
    return vf


@pytest.fixture()
def model_file(tmp_path: Path) -> Path:
    """Create a fake model file."""
    mf = tmp_path / "model.task"
    mf.write_bytes(b"fake model")
    return mf


class TestCacheRoundTrip:
    """Write/read cycle produces equivalent data."""

    def test_put_then_get_returns_sequence(
        self, tmp_path: Path, video_file: Path, model_file: Path
    ) -> None:
        cache_dir = tmp_path / "cache"
        cache = AnalysisCache(str(cache_dir), str(model_file))
        seq = _make_test_sequence()
        config_hash = "abc123"

        cache.put(str(video_file), config_hash, seq)
        result = cache.get(str(video_file), config_hash)

        assert result is not None
        assert result.metadata.file_path == seq.metadata.file_path
        assert result.metadata.total_frames == seq.metadata.total_frames
        assert result.metadata.fps == seq.metadata.fps
        assert len(result.poses) == len(seq.poses)

        # Verify landmark data preserved
        for i, (orig, loaded) in enumerate(zip(seq.poses, result.poses)):
            assert orig is not None
            assert loaded is not None
            assert loaded.timestamp_ms == orig.timestamp_ms
            assert loaded.body_scale == pytest.approx(orig.body_scale)
            for j in range(NUM_LANDMARKS):
                orig_lm = orig.landmarks_2d[j]
                loaded_lm = loaded.landmarks_2d[j]
                assert orig_lm is not None
                assert loaded_lm is not None
                assert loaded_lm[0] == pytest.approx(orig_lm[0])
                assert loaded_lm[1] == pytest.approx(orig_lm[1])

    def test_joint_angles_preserved(
        self, tmp_path: Path, video_file: Path, model_file: Path
    ) -> None:
        cache_dir = tmp_path / "cache"
        cache = AnalysisCache(str(cache_dir), str(model_file))
        seq = _make_test_sequence()

        cache.put(str(video_file), "hash1", seq)
        result = cache.get(str(video_file), "hash1")

        assert result is not None
        assert result.joint_angles[0] is not None
        assert result.joint_angles[0]["left_elbow"] == pytest.approx(90.0)
        assert result.joint_angles[0]["right_elbow"] is None


class TestCacheMiss:
    """Cache returns None when entry doesn't exist."""

    def test_get_nonexistent_returns_none(
        self, tmp_path: Path, video_file: Path, model_file: Path
    ) -> None:
        cache_dir = tmp_path / "cache"
        cache = AnalysisCache(str(cache_dir), str(model_file))
        result = cache.get(str(video_file), "nonexistent_hash")
        assert result is None


class TestCacheInvalidation:
    """Cache invalidates on mtime/config changes."""

    def test_invalidate_on_video_mtime_change(
        self, tmp_path: Path, video_file: Path, model_file: Path
    ) -> None:
        cache_dir = tmp_path / "cache"
        cache = AnalysisCache(str(cache_dir), str(model_file))
        seq = _make_test_sequence()

        cache.put(str(video_file), "hash1", seq)
        assert cache.get(str(video_file), "hash1") is not None

        # Change video mtime
        time.sleep(0.05)
        video_file.write_bytes(b"modified content")

        # Cache should be invalid now
        assert cache.get(str(video_file), "hash1") is None

    def test_invalidate_on_config_hash_change(
        self, tmp_path: Path, video_file: Path, model_file: Path
    ) -> None:
        cache_dir = tmp_path / "cache"
        cache = AnalysisCache(str(cache_dir), str(model_file))
        seq = _make_test_sequence()

        cache.put(str(video_file), "hash_v1", seq)
        # Different config hash → different cache key → miss
        result = cache.get(str(video_file), "hash_v2")
        assert result is None

    def test_invalidate_on_model_mtime_change(
        self, tmp_path: Path, video_file: Path, model_file: Path
    ) -> None:
        cache_dir = tmp_path / "cache"
        cache = AnalysisCache(str(cache_dir), str(model_file))
        seq = _make_test_sequence()

        cache.put(str(video_file), "hash1", seq)
        assert cache.get(str(video_file), "hash1") is not None

        # Change model mtime
        time.sleep(0.05)
        model_file.write_bytes(b"updated model")

        assert cache.get(str(video_file), "hash1") is None


class TestCacheCorruption:
    """Corrupted cache is discarded gracefully."""

    def test_corrupted_meta_returns_none(
        self, tmp_path: Path, video_file: Path, model_file: Path
    ) -> None:
        cache_dir = tmp_path / "cache"
        cache = AnalysisCache(str(cache_dir), str(model_file))
        seq = _make_test_sequence()

        cache.put(str(video_file), "hash1", seq)

        # Corrupt the meta file
        for meta_file in cache_dir.glob("*.meta.json.gz"):
            meta_file.write_bytes(b"corrupted data")

        result = cache.get(str(video_file), "hash1")
        assert result is None

    def test_corrupted_npz_returns_none(
        self, tmp_path: Path, video_file: Path, model_file: Path
    ) -> None:
        cache_dir = tmp_path / "cache"
        cache = AnalysisCache(str(cache_dir), str(model_file))
        seq = _make_test_sequence()

        cache.put(str(video_file), "hash1", seq)

        # Corrupt the npz file
        for npz_file in cache_dir.glob("*.data.npz"):
            npz_file.write_bytes(b"corrupted numpy data")

        result = cache.get(str(video_file), "hash1")
        assert result is None


class TestCacheDisabled:
    """Cache with no directory is effectively disabled."""

    def test_empty_directory_disables_cache(
        self, video_file: Path, model_file: Path
    ) -> None:
        cache = AnalysisCache("", str(model_file))
        seq = _make_test_sequence()

        # put does nothing, get returns None
        cache.put(str(video_file), "hash1", seq)
        assert cache.get(str(video_file), "hash1") is None


class TestNoPpickle:
    """Verify no pickle is used in serialization."""

    def test_cache_files_are_not_pickle(
        self, tmp_path: Path, video_file: Path, model_file: Path
    ) -> None:
        cache_dir = tmp_path / "cache"
        cache = AnalysisCache(str(cache_dir), str(model_file))
        seq = _make_test_sequence()
        cache.put(str(video_file), "hash1", seq)

        # Check meta file is valid gzipped JSON
        for meta_file in cache_dir.glob("*.meta.json.gz"):
            with gzip.open(meta_file, "rt") as f:
                data = json.load(f)
            assert isinstance(data, dict)
            assert "video_path" in data

        # Check npz file loads without allow_pickle
        for npz_file in cache_dir.glob("*.data.npz"):
            loaded = np.load(str(npz_file), allow_pickle=False)
            assert "valid" in loaded
            assert "landmarks_2d" in loaded


class TestConfigHash:
    """Test config hash computation."""

    def test_same_values_produce_same_hash(self) -> None:
        h1 = compute_config_hash({"a": 1, "b": "two"})
        h2 = compute_config_hash({"a": 1, "b": "two"})
        assert h1 == h2

    def test_different_values_produce_different_hash(self) -> None:
        h1 = compute_config_hash({"threshold": 0.5})
        h2 = compute_config_hash({"threshold": 0.7})
        assert h1 != h2
