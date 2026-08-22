"""Unit tests for ScoringEngine orchestrator.

Tests the full pipeline: align → compare → aggregate → rate → feedback.
Uses synthetic deterministic data only.
"""

import pytest

from opendance.config.models import AppConfig
from opendance.motion.landmarks import NUM_LANDMARKS
from opendance.motion.motion_result import LandmarkMotion, MotionFeatures
from opendance.motion.normalized_pose import NormalizedPose
from opendance.scoring.engine import ScoringEngine
from opendance.scoring.models import EventRating
from opendance.video.reference_sequence import ReferenceSequence, VideoMetadata


def _make_pose(
    timestamp_ms: int = 0,
    x: float = 0.0,
    y: float = 0.0,
) -> NormalizedPose:
    return NormalizedPose(
        timestamp_ms=timestamp_ms,
        landmarks_2d=tuple((x, y, 0.0) for _ in range(NUM_LANDMARKS)),
        landmarks_3d=None,
        visibilities=tuple(1.0 for _ in range(NUM_LANDMARKS)),
        presences=tuple(1.0 for _ in range(NUM_LANDMARKS)),
        body_center=(0.0, 0.0, 0.0),
        body_scale=1.0,
        valid=True,
    )


def _make_motion(speed: float = 1.0) -> MotionFeatures:
    lm = LandmarkMotion(
        velocity_x=speed, velocity_y=0.0, velocity_z=0.0,
        speed=speed, acceleration=None,
        direction_x=1.0 if speed > 0 else 0.0,
        direction_y=0.0, direction_z=0.0,
    )
    return MotionFeatures(
        landmark_motions=tuple(lm for _ in range(NUM_LANDMARKS)),
        timestamp_ms=0,
        dt_seconds=0.033,
    )


def _make_reference(num_frames: int = 10, duration_s: float = 1.0) -> ReferenceSequence:
    poses = tuple(_make_pose(timestamp_ms=int(i * duration_s * 1000 / max(num_frames - 1, 1)))
                  for i in range(num_frames))
    angles = tuple({"left_elbow": 90.0, "right_elbow": -45.0} for _ in range(num_frames))
    motions = tuple(_make_motion(1.0) for _ in range(num_frames))
    return ReferenceSequence(
        metadata=VideoMetadata(
            file_path="/test.mp4",
            total_frames=num_frames * 3,
            fps=30.0,
            duration_seconds=duration_s,
            width=640,
            height=480,
        ),
        poses=poses,
        motion_features=motions,
        joint_angles=angles,
    )


@pytest.fixture()
def config() -> AppConfig:
    return AppConfig()


@pytest.fixture()
def reference() -> ReferenceSequence:
    return _make_reference()


class TestScoringEnginePerfectMatch:
    """Identical player and reference → PERFECT."""

    def test_perfect_score(self, config: AppConfig, reference: ReferenceSequence) -> None:
        engine = ScoringEngine(reference, config)
        player_pose = _make_pose(timestamp_ms=500)
        player_angles = {"left_elbow": 90.0, "right_elbow": -45.0}
        player_motion = _make_motion(1.0)

        result = engine.score_frame(player_pose, player_angles, player_motion)

        assert result.pose_score == pytest.approx(100.0)
        assert result.angle_score == pytest.approx(100.0)
        assert result.combined_score is not None
        assert result.combined_score >= 90.0
        assert result.event_rating == EventRating.PERFECT


class TestScoringEngineKnownMismatch:
    """Known non-perfect comparison."""

    def test_pose_displacement_reduces_score(
        self, config: AppConfig, reference: ReferenceSequence
    ) -> None:
        engine = ScoringEngine(reference, config)
        player_pose = _make_pose(timestamp_ms=500, x=0.25, y=0.0)
        player_angles = {"left_elbow": 90.0, "right_elbow": -45.0}
        player_motion = _make_motion(1.0)

        result = engine.score_frame(player_pose, player_angles, player_motion)

        assert result.pose_score is not None
        assert result.pose_score < 100.0
        # 0.25 mean distance * 200 = 50 deduction → score ~50
        assert result.pose_score == pytest.approx(50.0)


class TestScoringEngineMissingData:
    """Missing data handling."""

    def test_missing_motion(self, config: AppConfig, reference: ReferenceSequence) -> None:
        engine = ScoringEngine(reference, config)
        player_pose = _make_pose(timestamp_ms=500)
        player_angles = {"left_elbow": 90.0, "right_elbow": -45.0}

        result = engine.score_frame(player_pose, player_angles, None)

        assert result.motion_score is None
        assert result.timing_score is None
        # Combined still computed from available scores
        assert result.combined_score is not None
        assert result.event_rating != EventRating.MISS

    def test_missing_angles(self, config: AppConfig, reference: ReferenceSequence) -> None:
        engine = ScoringEngine(reference, config)
        player_pose = _make_pose(timestamp_ms=500)

        result = engine.score_frame(player_pose, {}, _make_motion(1.0))

        assert result.angle_score is None
        assert result.combined_score is not None

    def test_invalid_pose(self, config: AppConfig, reference: ReferenceSequence) -> None:
        engine = ScoringEngine(reference, config)
        invalid = NormalizedPose.invalid(timestamp_ms=500)

        results = engine.score_sequence([invalid], [{}], [None])

        assert results[0] is None

    def test_all_data_unavailable(self, config: AppConfig) -> None:
        """Reference with None poses → all scores None → MISS."""
        ref = ReferenceSequence(
            metadata=VideoMetadata("/t.mp4", 10, 30.0, 1.0, 640, 480),
            poses=tuple(None for _ in range(10)),
            motion_features=tuple(None for _ in range(10)),
            joint_angles=tuple(None for _ in range(10)),
        )
        engine = ScoringEngine(ref, AppConfig())
        player_pose = _make_pose(timestamp_ms=500)

        result = engine.score_frame(player_pose, {}, None)

        assert result.pose_score is None
        assert result.combined_score is None
        assert result.event_rating == EventRating.MISS


class TestScoringEngineAlignment:
    """Nearest-frame alignment."""

    def test_aligns_to_nearest_frame(self, config: AppConfig) -> None:
        ref = _make_reference(num_frames=10, duration_s=1.0)
        engine = ScoringEngine(ref, config)
        # timestamp 0 → frame 0, timestamp 1000 → frame 9
        result_start = engine.score_frame(_make_pose(0), {"left_elbow": 90.0}, _make_motion())
        result_end = engine.score_frame(_make_pose(1000), {"left_elbow": 90.0}, _make_motion())
        # Both should produce valid results
        assert result_start.combined_score is not None
        assert result_end.combined_score is not None


class TestScoringEngineFeedback:
    """Feedback propagation."""

    def test_feedback_generated_for_errors(
        self, config: AppConfig, reference: ReferenceSequence
    ) -> None:
        engine = ScoringEngine(reference, config)
        player_pose = _make_pose(timestamp_ms=500, x=0.3, y=0.0)
        player_angles = {"left_elbow": 90.0, "right_elbow": -45.0}

        result = engine.score_frame(player_pose, player_angles, _make_motion(1.0))

        # Position feedback should be present (distance 0.3 > threshold)
        pos_feedback = [f for f in result.feedback if f.issue_type == "position_off"]
        assert len(pos_feedback) > 0


class TestScoringEngineDeterminism:
    """Deterministic repeated execution."""

    def test_same_input_same_output(self, config: AppConfig, reference: ReferenceSequence) -> None:
        engine = ScoringEngine(reference, config)
        player_pose = _make_pose(timestamp_ms=333, x=0.1, y=0.05)
        player_angles = {"left_elbow": 75.0, "right_elbow": -30.0}
        player_motion = _make_motion(0.8)

        r1 = engine.score_frame(player_pose, player_angles, player_motion)
        r2 = engine.score_frame(player_pose, player_angles, player_motion)

        assert r1.pose_score == r2.pose_score
        assert r1.angle_score == r2.angle_score
        assert r1.motion_score == r2.motion_score
        assert r1.timing_score == r2.timing_score
        assert r1.combined_score == r2.combined_score
        assert r1.event_rating == r2.event_rating


class TestScoringEngineSequence:
    """Full sequence scoring."""

    def test_sequence_length_matches(self, config: AppConfig, reference: ReferenceSequence) -> None:
        engine = ScoringEngine(reference, config)
        poses = [_make_pose(i * 100) for i in range(5)]
        angles = [{"left_elbow": 90.0} for _ in range(5)]
        motions = [_make_motion(1.0) for _ in range(5)]

        results = engine.score_sequence(poses, angles, motions)

        assert len(results) == 5
        assert all(r is not None for r in results)

    def test_none_pose_produces_none_result(
        self, config: AppConfig, reference: ReferenceSequence
    ) -> None:
        engine = ScoringEngine(reference, config)
        poses: list[NormalizedPose | None] = [_make_pose(0), None, _make_pose(200)]
        angles: list[dict[str, float | None] | None] = [{}, None, {}]
        motions: list[MotionFeatures | None] = [None, None, None]

        results = engine.score_sequence(poses, angles, motions)

        assert results[0] is not None
        assert results[1] is None
        assert results[2] is not None
