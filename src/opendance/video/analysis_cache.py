"""Analysis cache: gzipped JSON metadata + numpy.savez_compressed arrays.

Stores derived numerical artifacts from reference video analysis.
Never stores raw frames. Never uses pickle.

Cache key: absolute video path + video mtime + config hash + model file metadata.
Disabled by default (auto_cache=False in ReferenceConfig).
"""

import gzip
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np

from opendance.motion.landmarks import NUM_LANDMARKS
from opendance.motion.normalized_pose import NormalizedPose
from opendance.video.reference_sequence import ReferenceSequence, VideoMetadata

logger = logging.getLogger(__name__)


def compute_config_hash(config_values: dict[str, Any]) -> str:
    """Compute a deterministic hash of configuration values."""
    serialized = json.dumps(config_values, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def _get_file_mtime(path: str) -> float:
    """Get file modification time. Returns 0.0 if file doesn't exist."""
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


class AnalysisCache:
    """Deterministic cache: gzipped JSON metadata + numpy.savez_compressed.

    Cache key components:
    - Absolute video file path
    - Video file mtime (os.path.getmtime)
    - Model file metadata (path + mtime of .task file)
    - Configuration hash (normalization + motion config values)

    Storage format per entry:
    - <hash>.meta.json.gz — VideoMetadata + cache key + config snapshot
    - <hash>.data.npz — numpy arrays for landmarks, visibilities, presences, etc.

    Disabled by default (auto_cache=False).
    """

    def __init__(self, cache_directory: str, model_path: str) -> None:
        self._cache_dir = Path(cache_directory) if cache_directory else None
        self._model_path = model_path

    def _compute_cache_key(self, video_path: str, config_hash: str) -> str:
        """Compute unique cache key from video + model + config."""
        abs_path = str(Path(video_path).resolve())
        video_mtime = _get_file_mtime(video_path)
        model_mtime = _get_file_mtime(self._model_path)

        key_data = json.dumps(
            {
                "video_path": abs_path,
                "video_mtime": video_mtime,
                "model_path": self._model_path,
                "model_mtime": model_mtime,
                "config_hash": config_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    def _meta_path(self, cache_key: str) -> Path:
        """Path for the gzipped JSON metadata file."""
        assert self._cache_dir is not None
        return self._cache_dir / f"{cache_key}.meta.json.gz"

    def _data_path(self, cache_key: str) -> Path:
        """Path for the numpy compressed arrays file."""
        assert self._cache_dir is not None
        return self._cache_dir / f"{cache_key}.data.npz"

    def get(self, video_path: str, config_hash: str) -> ReferenceSequence | None:
        """Load cached analysis if valid. Returns None on cache miss or invalid."""
        if self._cache_dir is None:
            return None

        cache_key = self._compute_cache_key(video_path, config_hash)
        meta_file = self._meta_path(cache_key)
        data_file = self._data_path(cache_key)

        if not meta_file.exists() or not data_file.exists():
            return None

        try:
            # Load and validate metadata
            with gzip.open(meta_file, "rt", encoding="utf-8") as f:
                meta_dict = json.load(f)

            # Validate cache key matches current state
            current_video_mtime = _get_file_mtime(video_path)
            current_model_mtime = _get_file_mtime(self._model_path)

            if meta_dict.get("video_mtime") != current_video_mtime:
                logger.info("Cache invalidated: video mtime changed for %s", video_path)
                return None
            if meta_dict.get("model_mtime") != current_model_mtime:
                logger.info("Cache invalidated: model mtime changed")
                return None
            if meta_dict.get("config_hash") != config_hash:
                logger.info("Cache invalidated: config hash changed")
                return None

            # Load numpy data
            npz_data = np.load(str(data_file), allow_pickle=False)

            # Reconstruct ReferenceSequence
            return self._deserialize(meta_dict, npz_data)

        except Exception as exc:
            logger.warning("Cache load failed for %s: %s. Discarding.", video_path, exc)
            self._remove_files(cache_key)
            return None

    def put(
        self, video_path: str, config_hash: str, sequence: ReferenceSequence
    ) -> None:
        """Store analysis result to cache."""
        if self._cache_dir is None:
            return

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cache_key = self._compute_cache_key(video_path, config_hash)

        try:
            meta_dict = self._serialize_metadata(video_path, config_hash, sequence)
            arrays = self._serialize_arrays(sequence)

            # Write gzipped JSON metadata
            meta_file = self._meta_path(cache_key)
            with gzip.open(meta_file, "wt", encoding="utf-8") as f:
                json.dump(meta_dict, f, separators=(",", ":"), sort_keys=True)

            # Write numpy arrays
            data_file = self._data_path(cache_key)
            np.savez_compressed(str(data_file), **arrays)  # type: ignore[arg-type]

            logger.info("Cache stored for %s", video_path)

        except Exception as exc:
            logger.warning("Cache write failed for %s: %s", video_path, exc)

    def invalidate(self, video_path: str) -> None:
        """Remove all cached results for a video (all config variants)."""
        if self._cache_dir is None or not self._cache_dir.exists():
            return

        # Remove any files matching this video's path pattern
        abs_path = str(Path(video_path).resolve())
        for meta_file in self._cache_dir.glob("*.meta.json.gz"):
            try:
                with gzip.open(meta_file, "rt", encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("video_path") == abs_path:
                    key = meta_file.stem.replace(".meta.json", "")
                    self._remove_files(key)
            except Exception:
                pass

    def _remove_files(self, cache_key: str) -> None:
        """Remove meta and data files for a cache key."""
        if self._cache_dir is None:
            return
        for suffix in (".meta.json.gz", ".data.npz"):
            path = self._cache_dir / f"{cache_key}{suffix}"
            if path.exists():
                path.unlink()

    def _serialize_metadata(
        self, video_path: str, config_hash: str, sequence: ReferenceSequence
    ) -> dict[str, Any]:
        """Serialize metadata + cache key to dict for JSON."""
        return {
            "video_path": str(Path(video_path).resolve()),
            "video_mtime": _get_file_mtime(video_path),
            "model_path": self._model_path,
            "model_mtime": _get_file_mtime(self._model_path),
            "config_hash": config_hash,
            "metadata": {
                "file_path": sequence.metadata.file_path,
                "total_frames": sequence.metadata.total_frames,
                "fps": sequence.metadata.fps,
                "duration_seconds": sequence.metadata.duration_seconds,
                "width": sequence.metadata.width,
                "height": sequence.metadata.height,
            },
            "num_poses": len(sequence.poses),
            "joint_angle_keys": list(
                (sequence.joint_angles[0] or {}).keys()
            )
            if sequence.joint_angles and sequence.joint_angles[0] is not None
            else [],
        }

    def _serialize_arrays(self, sequence: ReferenceSequence) -> dict[str, np.ndarray]:
        """Convert sequence data to numpy arrays for savez_compressed."""
        n = len(sequence.poses)
        # Validity mask
        valid = np.array([p is not None and p.valid for p in sequence.poses], dtype=np.bool_)

        # Timestamps
        timestamps = np.array(
            [p.timestamp_ms if p is not None else 0 for p in sequence.poses],
            dtype=np.int64,
        )

        # Landmarks 2D: (n, 33, 3) with NaN for None
        lm2d = np.full((n, NUM_LANDMARKS, 3), np.nan, dtype=np.float64)
        for i, pose in enumerate(sequence.poses):
            if pose is not None and pose.valid and pose.landmarks_2d is not None:
                for j, lm in enumerate(pose.landmarks_2d):
                    if lm is not None:
                        lm2d[i, j] = lm

        # Visibilities and presences
        vis = np.zeros((n, NUM_LANDMARKS), dtype=np.float64)
        pres = np.zeros((n, NUM_LANDMARKS), dtype=np.float64)
        for i, pose in enumerate(sequence.poses):
            if pose is not None and pose.valid:
                vis[i] = pose.visibilities
                pres[i] = pose.presences

        # Body center and scale
        centers = np.zeros((n, 3), dtype=np.float64)
        scales = np.zeros(n, dtype=np.float64)
        for i, pose in enumerate(sequence.poses):
            if pose is not None and pose.valid:
                centers[i] = pose.body_center
                scales[i] = pose.body_scale

        # Joint angles: (n, num_joints) with NaN for None
        joint_keys: list[str] = []
        if sequence.joint_angles:
            for angles in sequence.joint_angles:
                if angles is not None:
                    joint_keys = list(angles.keys())
                    break

        angles_arr = np.full((n, len(joint_keys)), np.nan, dtype=np.float64)
        for i, angles in enumerate(sequence.joint_angles):
            if angles is not None:
                for j, key in enumerate(joint_keys):
                    val = angles.get(key)
                    if val is not None:
                        angles_arr[i, j] = val

        return {
            "valid": valid,
            "timestamps": timestamps,
            "landmarks_2d": lm2d,
            "visibilities": vis,
            "presences": pres,
            "centers": centers,
            "scales": scales,
            "angles": angles_arr,
        }

    def _deserialize(
        self, meta_dict: dict[str, Any], npz_data: Any
    ) -> ReferenceSequence:
        """Reconstruct ReferenceSequence from cached metadata + arrays."""
        meta_info = meta_dict["metadata"]
        metadata = VideoMetadata(
            file_path=meta_info["file_path"],
            total_frames=meta_info["total_frames"],
            fps=meta_info["fps"],
            duration_seconds=meta_info["duration_seconds"],
            width=meta_info["width"],
            height=meta_info["height"],
        )

        valid = npz_data["valid"]
        timestamps = npz_data["timestamps"]
        lm2d = npz_data["landmarks_2d"]
        vis = npz_data["visibilities"]
        pres = npz_data["presences"]
        centers = npz_data["centers"]
        scales = npz_data["scales"]
        angles_arr = npz_data["angles"]
        joint_keys = meta_dict.get("joint_angle_keys", [])

        n = len(valid)
        poses: list[NormalizedPose | None] = []
        joint_angles: list[dict[str, float | None] | None] = []

        for i in range(n):
            if not valid[i]:
                poses.append(None)
                joint_angles.append(None)
                continue

            lm2d_tuples: list[tuple[float, float, float] | None] = []
            for j in range(NUM_LANDMARKS):
                if np.isnan(lm2d[i, j, 0]):
                    lm2d_tuples.append(None)
                else:
                    lm2d_tuples.append(
                        (float(lm2d[i, j, 0]), float(lm2d[i, j, 1]), float(lm2d[i, j, 2]))
                    )

            pose = NormalizedPose(
                timestamp_ms=int(timestamps[i]),
                landmarks_2d=tuple(lm2d_tuples),
                landmarks_3d=None,
                visibilities=tuple(float(v) for v in vis[i]),
                presences=tuple(float(p) for p in pres[i]),
                body_center=(float(centers[i, 0]), float(centers[i, 1]), float(centers[i, 2])),
                body_scale=float(scales[i]),
                valid=True,
            )
            poses.append(pose)

            # Reconstruct angles
            if len(joint_keys) > 0:
                frame_angles: dict[str, float | None] = {}
                for j, key in enumerate(joint_keys):
                    val = float(angles_arr[i, j])
                    frame_angles[key] = val if not np.isnan(val) else None
                joint_angles.append(frame_angles)
            else:
                joint_angles.append(None)

        # Motion features are recomputed from poses (not cached separately for simplicity)
        from opendance.motion.features import compute_sequence_motion

        motion_results = compute_sequence_motion(poses)

        return ReferenceSequence(
            metadata=metadata,
            poses=tuple(poses),
            motion_features=tuple(motion_results),
            joint_angles=tuple(joint_angles),
        )
