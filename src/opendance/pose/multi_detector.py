"""Multi-person pose detection with explicit subject tracking.

Provides persistent identity tracking with:
- Explicit user selection (select_subject)
- Hard identity lock (never switches silently)
- Composite identity scoring (trajectory + geometry + area)
- Ambiguity gate (UNCERTAIN/OCCLUDED rather than wrong person)
- Manual correction API (correct_subject → new anchor → retrack)
- Confidence scoring

Safety rule: IDENTITY CORRECTNESS > DETECTION CONTINUITY.
"""

import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np

from opendance.config.models import PoseConfig
from opendance.pose.result import Landmark, PoseResult, WorldLandmark

logger = logging.getLogger(__name__)

# Identity matching weights
W_TRAJECTORY = 0.50
W_GEOMETRY = 0.35
W_AREA = 0.15

# Ambiguity: if gap between best and second < margin * best → UNCERTAIN
AMBIGUITY_MARGIN = 0.25

# Max distance from predicted center to even consider a candidate
MAX_MATCH_DISTANCE = 0.30

_VIS_THRESHOLD = 0.5


class TrackState(Enum):
    """Tracking state for the subject."""

    UNLOCKED = "UNLOCKED"
    TRACKING = "TRACKING"
    OCCLUDED = "OCCLUDED"
    LOST = "LOST"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class PoseCandidate:
    """A single detected pose candidate with selection metadata."""

    pose_result: PoseResult
    body_area: float
    center_x: float
    center_y: float
    visible_landmarks: int


@dataclass
class SubjectTrack:
    """Persistent identity of the tracked subject.

    The subject_id remains constant for the lifetime of the track,
    even across occlusions, corrections, and recovery.
    """

    subject_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    state: TrackState = TrackState.UNLOCKED
    confidence: float = 0.0
    last_center: tuple[float, float] = (0.5, 0.5)
    prev_center: tuple[float, float] | None = None
    last_area: float = 0.0
    last_geometry: list[tuple[float, float]] | None = None
    lost_frame_count: int = 0
    anchor_frame: int = 0
    anchor_center: tuple[float, float] = (0.5, 0.5)
    anchor_area: float = 0.0
    anchor_geometry: list[tuple[float, float]] | None = None
    history_centers: list[tuple[float, float]] = field(
        default_factory=list
    )
    locked: bool = False


def compute_body_area(
    landmarks: tuple[Landmark, ...],
    visibility_threshold: float = 0.5,
) -> float:
    """Compute normalized bounding-box area from visible landmarks."""
    visible = [
        (lm.x, lm.y)
        for lm in landmarks
        if lm.visibility >= visibility_threshold
    ]
    if len(visible) < 3:
        return 0.0
    xs = [p[0] for p in visible]
    ys = [p[1] for p in visible]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


def compute_center(
    landmarks: tuple[Landmark, ...],
    visibility_threshold: float = 0.5,
) -> tuple[float, float]:
    """Compute center of visible landmarks."""
    visible = [
        (lm.x, lm.y)
        for lm in landmarks
        if lm.visibility >= visibility_threshold
    ]
    if not visible:
        return (0.5, 0.5)
    xs = [p[0] for p in visible]
    ys = [p[1] for p in visible]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def count_visible(
    landmarks: tuple[Landmark, ...],
    visibility_threshold: float = 0.5,
) -> int:
    """Count landmarks meeting visibility threshold."""
    return sum(
        1 for lm in landmarks if lm.visibility >= visibility_threshold
    )


def _euclidean(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return float((dx * dx + dy * dy) ** 0.5)


def _compute_geometry_vector(
    landmarks: tuple[Landmark, ...],
    center: tuple[float, float],
    area: float,
) -> list[tuple[float, float]] | None:
    """Body-relative landmark positions for geometry comparison."""
    if area <= 0:
        return None
    scale = float(area ** 0.5)
    if scale < 1e-6:
        return None
    result: list[tuple[float, float]] = []
    for lm in landmarks:
        if lm.visibility >= _VIS_THRESHOLD:
            result.append(
                ((lm.x - center[0]) / scale, (lm.y - center[1]) / scale)
            )
        else:
            result.append((float("nan"), float("nan")))
    return result


def _geometry_similarity(
    geo_a: list[tuple[float, float]] | None,
    geo_b: list[tuple[float, float]] | None,
) -> float | None:
    """Distance between two geometry vectors. Lower = more similar."""
    if geo_a is None or geo_b is None:
        return None
    if len(geo_a) != len(geo_b):
        return None
    diffs: list[float] = []
    for (ax, ay), (bx, by) in zip(geo_a, geo_b):
        if ax != ax or bx != bx:  # noqa: PLR0124
            continue
        diffs.append(float(((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5))
    if len(diffs) < 5:
        return None
    return float(np.mean(diffs))


class MultiPoseDetector:
    """Multi-person detector with explicit subject tracking.

    Usage:
        detector = MultiPoseDetector(config)
        candidates = detector.detect_all(frame, ts)
        # User selects subject:
        detector.select_subject(candidate_index)
        # Subsequent frames:
        result = detector.detect(frame, ts)
        # Manual correction if needed:
        detector.correct_subject(frame_idx, candidate_index)
    """

    def __init__(
        self,
        config: PoseConfig,
        max_lost_frames: int = 90,
        ambiguity_margin: float = AMBIGUITY_MARGIN,
    ) -> None:
        model_path = Path(config.model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"MediaPipe pose model not found at: "
                f"{model_path.resolve()}"
            )

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
            num_poses=config.max_poses,
        )
        self._landmarker = PoseLandmarker.create_from_options(options)
        self._config = config
        self._max_lost_frames = max_lost_frames
        self._ambiguity_margin = ambiguity_margin

        self._subject: SubjectTrack = SubjectTrack()
        self._frame_index: int = 0
        self._last_candidates: list[PoseCandidate] = []

    # === Public Properties ===

    @property
    def track_state(self) -> TrackState:
        return self._subject.state

    @property
    def lost_frame_count(self) -> int:
        return self._subject.lost_frame_count

    @property
    def is_locked(self) -> bool:
        return self._subject.locked

    @property
    def subject(self) -> SubjectTrack:
        """Current subject track (read-only access)."""
        return self._subject

    @property
    def last_candidates(self) -> list[PoseCandidate]:
        """Candidates from the most recent detect_all call."""
        return self._last_candidates

    # === Subject Selection ===

    def select_subject(
        self, candidate_index: int, candidates: list[PoseCandidate] | None = None
    ) -> None:
        """Explicitly select a candidate as the subject.

        Args:
            candidate_index: Index into candidates list.
            candidates: If None, uses last_candidates.

        Once selected, the subject is LOCKED and cannot be
        changed except by correct_subject or reset_tracking.
        """
        cands = candidates if candidates is not None else self._last_candidates
        if candidate_index < 0 or candidate_index >= len(cands):
            raise IndexError(
                f"candidate_index {candidate_index} out of range "
                f"(0–{len(cands) - 1})"
            )
        selected = cands[candidate_index]
        self._lock_subject(selected, self._frame_index)

    def correct_subject(
        self,
        frame_index: int,
        candidate_index: int,
        candidates: list[PoseCandidate] | None = None,
    ) -> None:
        """Manual correction: re-anchor subject to a specific candidate.

        Creates a new anchor at frame_index. The subject_id remains
        the same — this is a correction, not a new subject.
        """
        cands = candidates if candidates is not None else self._last_candidates
        if candidate_index < 0 or candidate_index >= len(cands):
            raise IndexError(
                f"candidate_index {candidate_index} out of range"
            )
        selected = cands[candidate_index]
        geo = _compute_geometry_vector(
            selected.pose_result.landmarks,
            (selected.center_x, selected.center_y),
            selected.body_area,
        )
        # Update tracking state without changing subject_id
        self._subject.state = TrackState.TRACKING
        self._subject.confidence = 1.0
        self._subject.prev_center = self._subject.last_center
        self._subject.last_center = (
            selected.center_x, selected.center_y
        )
        self._subject.last_area = selected.body_area
        self._subject.last_geometry = geo
        self._subject.lost_frame_count = 0
        self._subject.anchor_frame = frame_index
        self._subject.anchor_center = (
            selected.center_x, selected.center_y
        )
        self._subject.anchor_area = selected.body_area
        self._subject.anchor_geometry = geo
        self._subject.history_centers.append(
            (selected.center_x, selected.center_y)
        )
        logger.info(
            "Subject %s corrected at frame %d",
            self._subject.subject_id, frame_index,
        )

    # === Detection ===

    def detect_all(
        self, frame: np.ndarray, timestamp_ms: int = 0
    ) -> list[PoseCandidate]:
        """Detect all poses in frame."""
        try:
            import cv2
            import mediapipe as mp

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB, data=rgb_frame
            )
            result = self._landmarker.detect_for_video(
                mp_image, timestamp_ms
            )

            if not result.pose_landmarks:
                self._last_candidates = []
                return []

            vis_thresh = self._config.skeleton_visibility_threshold
            candidates: list[PoseCandidate] = []

            for i, pose_landmarks in enumerate(result.pose_landmarks):
                landmarks = tuple(
                    Landmark(
                        x=lm.x, y=lm.y, z=lm.z,
                        visibility=getattr(lm, "visibility", 0.0),
                        presence=getattr(lm, "presence", 0.0),
                    )
                    for lm in pose_landmarks
                )
                world_landmarks: tuple[WorldLandmark, ...] = ()
                if (
                    result.pose_world_landmarks
                    and i < len(result.pose_world_landmarks)
                ):
                    wl_list = result.pose_world_landmarks[i]
                    world_landmarks = tuple(
                        WorldLandmark(
                            x=wl.x, y=wl.y, z=wl.z,
                            visibility=getattr(wl, "visibility", 0.0),
                            presence=getattr(wl, "presence", 0.0),
                        )
                        for wl in wl_list
                    )

                pose_result = PoseResult(
                    landmarks=landmarks,
                    world_landmarks=world_landmarks,
                    timestamp_ms=timestamp_ms,
                )
                area = compute_body_area(landmarks, vis_thresh)
                cx, cy = compute_center(landmarks, vis_thresh)
                vis_count = count_visible(landmarks, vis_thresh)
                candidates.append(PoseCandidate(
                    pose_result=pose_result,
                    body_area=area,
                    center_x=cx,
                    center_y=cy,
                    visible_landmarks=vis_count,
                ))

            self._last_candidates = candidates
            return candidates

        except Exception as exc:
            logger.warning("Multi-pose detection failed: %s", exc)
            self._last_candidates = []
            return []

    def select_primary(
        self, candidates: list[PoseCandidate]
    ) -> PoseResult:
        """Track subject among candidates.

        If no subject is locked, auto-selects the largest candidate.
        Once locked, uses identity matching with ambiguity gate.
        """
        self._last_candidates = candidates
        self._frame_index += 1

        # === UNLOCKED: auto-select largest ===
        if not self._subject.locked:
            if not candidates:
                return PoseResult.empty(timestamp_ms=0)
            largest_idx = max(
                range(len(candidates)),
                key=lambda i: candidates[i].body_area,
            )
            self._lock_subject(candidates[largest_idx], self._frame_index)
            return candidates[largest_idx].pose_result

        # === LOCKED: identity matching ===
        if not candidates:
            return self._handle_missing()

        # Predict center
        predicted = self._predicted_center()

        # Pre-filter by distance to predicted center
        nearby: list[tuple[int, PoseCandidate]] = []
        for i, c in enumerate(candidates):
            d = _euclidean((c.center_x, c.center_y), predicted)
            if d <= MAX_MATCH_DISTANCE:
                nearby.append((i, c))

        if not nearby:
            return self._handle_missing()

        # Score each nearby candidate
        scored: list[tuple[float, int, PoseCandidate]] = []
        for idx, c in nearby:
            score = self._identity_score(c)
            scored.append((score, idx, c))
        scored.sort(key=lambda x: x[0])

        best_score, best_idx, best_cand = scored[0]

        # === AMBIGUITY GATE ===
        if len(scored) >= 2:
            second_score = scored[1][0]
            gap = second_score - best_score
            threshold = max(best_score * self._ambiguity_margin, 0.02)
            if gap < threshold:
                # Cannot distinguish — prefer UNCERTAIN over wrong
                self._subject.state = TrackState.UNCERTAIN
                self._subject.confidence = 0.3
                self._subject.lost_frame_count += 1
                return PoseResult.empty(timestamp_ms=0)

        # Clear winner
        confidence = max(0.0, min(1.0, 1.0 - best_score))
        self._update_tracking(best_cand, confidence)
        return best_cand.pose_result

    def detect(
        self, frame: np.ndarray, timestamp_ms: int = 0
    ) -> PoseResult:
        """Detect and track subject (drop-in API)."""
        candidates = self.detect_all(frame, timestamp_ms)
        result = self.select_primary(candidates)
        if result.is_empty:
            return PoseResult.empty(timestamp_ms=timestamp_ms)
        return result

    def reset_tracking(self) -> None:
        """Reset subject — creates new SubjectTrack."""
        self._subject = SubjectTrack()
        self._frame_index = 0

    def close(self) -> None:
        """Release MediaPipe resources."""
        if hasattr(self, "_landmarker") and self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception as exc:
                logger.warning(
                    "Error closing MultiPoseDetector: %s", exc
                )
            self._landmarker = None  # type: ignore[assignment]

    # === Internal ===

    def _lock_subject(
        self, candidate: PoseCandidate, frame_index: int
    ) -> None:
        """Lock identity onto candidate."""
        geo = _compute_geometry_vector(
            candidate.pose_result.landmarks,
            (candidate.center_x, candidate.center_y),
            candidate.body_area,
        )
        center = (candidate.center_x, candidate.center_y)
        self._subject.locked = True
        self._subject.state = TrackState.TRACKING
        self._subject.confidence = 1.0
        self._subject.last_center = center
        self._subject.prev_center = None
        self._subject.last_area = candidate.body_area
        self._subject.last_geometry = geo
        self._subject.lost_frame_count = 0
        self._subject.anchor_frame = frame_index
        self._subject.anchor_center = center
        self._subject.anchor_area = candidate.body_area
        self._subject.anchor_geometry = geo
        self._subject.history_centers = [center]

    def _predicted_center(self) -> tuple[float, float]:
        """Linear velocity extrapolation."""
        if self._subject.prev_center is None:
            return self._subject.last_center
        vx = (
            self._subject.last_center[0]
            - self._subject.prev_center[0]
        )
        vy = (
            self._subject.last_center[1]
            - self._subject.prev_center[1]
        )
        return (
            self._subject.last_center[0] + vx,
            self._subject.last_center[1] + vy,
        )

    def _identity_score(self, candidate: PoseCandidate) -> float:
        """Composite identity cost. Lower = better match."""
        predicted = self._predicted_center()

        # Trajectory cost
        traj_dist = _euclidean(
            (candidate.center_x, candidate.center_y), predicted
        )
        traj_cost = min(traj_dist / 0.3, 2.0)

        # Geometry cost
        cand_geo = _compute_geometry_vector(
            candidate.pose_result.landmarks,
            (candidate.center_x, candidate.center_y),
            candidate.body_area,
        )
        geo_dist = _geometry_similarity(
            self._subject.last_geometry, cand_geo
        )
        if geo_dist is not None:
            geo_cost = min(geo_dist / 2.0, 2.0)
        else:
            geo_cost = 0.5

        # Area cost
        if self._subject.last_area > 0:
            ratio = candidate.body_area / self._subject.last_area
            area_cost = min(abs(ratio - 1.0), 2.0)
        else:
            area_cost = 0.0

        return (
            traj_cost * W_TRAJECTORY
            + geo_cost * W_GEOMETRY
            + area_cost * W_AREA
        )

    def _update_tracking(
        self, candidate: PoseCandidate, confidence: float
    ) -> None:
        """Update subject state after successful match."""
        center = (candidate.center_x, candidate.center_y)
        geo = _compute_geometry_vector(
            candidate.pose_result.landmarks,
            center,
            candidate.body_area,
        )
        self._subject.state = TrackState.TRACKING
        self._subject.confidence = confidence
        self._subject.prev_center = self._subject.last_center
        self._subject.last_center = center
        self._subject.last_area = candidate.body_area
        self._subject.last_geometry = geo
        self._subject.lost_frame_count = 0
        # Keep history bounded
        self._subject.history_centers.append(center)
        if len(self._subject.history_centers) > 60:
            self._subject.history_centers = (
                self._subject.history_centers[-60:]
            )

    def _handle_missing(self) -> PoseResult:
        """Subject not found — OCCLUDED/LOST, never switch."""
        self._subject.lost_frame_count += 1
        if self._subject.lost_frame_count <= 5:
            self._subject.state = TrackState.OCCLUDED
            self._subject.confidence = max(
                0.0, 0.5 - self._subject.lost_frame_count * 0.1
            )
        else:
            self._subject.state = TrackState.LOST
            self._subject.confidence = 0.0
        return PoseResult.empty(timestamp_ms=0)
