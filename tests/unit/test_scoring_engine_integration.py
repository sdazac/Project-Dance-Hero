"""Integration tests for ScoringEngine — full pipeline verification.

Tests the complete orchestration: align → compare → aggregate → rate → feedback.
Covers: complete comparison, partial/missing data, sequence behavior,
alignment, configuration propagation, determinism, and immutability.
"""

import copy

import pytest

from opendance.config.models import (
    AppConfig,
    ComparisonConfig,
    ScoringThresholds,
)
from opendance.motion.landmarks import NUM_LANDMARKS
from opendance.motion.motion_result import LandmarkMotion, MotionFeatures
from opendance.motion.normalized_pose import NormalizedPose
from opendance.scoring.engine import ScoringEngine
from opendance.scoring.models import EventRating
from opendance.video.reference_sequence import ReferenceSequence, VideoMetadata

# --- Helpers ---

def _pose(ts: int = 0, x: float = 0.0, y: float = 0.0) -> NormalizedPose:
    return NormalizedPose(
        timestamp_ms=ts,
        landmarks_2d=tuple((x, y, 0.0) for _ in range(NUM_LANDMARKS)),
        landmarks_3d=None,
        visibilities=tuple(1.0 for _ in range(NUM_LANDMARKS)),
        presences=tuple(1.0 for _ in range(NUM_LANDMARKS)),
        body_center=(0.0, 0.0, 0.0),
        body_scale=1.0,
        valid=True,
    )


def _motion(speed: float = 1.0) -> MotionFeatures:
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


def _ref(n: int = 10, duration: float = 1.0) -> ReferenceSequence:
    poses = tuple(
        _pose(ts=int(i * duration * 1000 / max(n - 1, 1))) for i in range(n)
    )
    angles = tuple(
        {"left_elbow": 90.0, "right_elbow": -45.0, "left_knee": 120.0}
        for _ in range(n)
    )
    motions = tuple(_motion(1.0) for _ in range(n))
    return ReferenceSequence(
        metadata=VideoMetadata("/ref.mp4", n * 3, 30.0, duration, 640, 480),
        poses=poses,
        motion_features=motions,
        joint_angles=angles,
    )


# --- Complete Pipeline ---

class TestCompletePipeline:
    """Full valid comparison with all data."""

    def test_all_scores_produced(self) -> None:
        engine = ScoringEngine(_ref(), AppConfig())
        result = engine.score_frame(
            _pose(ts=500), {"left_elbow": 90.0, "right_elbow": -45.0}, _motion(1.0)
        )
        assert result.pose_score is not None
        assert result.angle_score is not None
        assert result.motion_score is not None
        assert result.timing_score is not None
        assert result.combined_score is not None
        assert result.event_rating != EventRating.MISS

    def test_perfect_match_produces_perfect(self) -> None:
        engine = ScoringEngine(_ref(), AppConfig())
        result = engine.score_frame(
            _pose(ts=500),
            {"left_elbow": 90.0, "right_elbow": -45.0, "left_knee": 120.0},
            _motion(1.0),
        )
        assert result.pose_score == pytest.approx(100.0)
        assert result.angle_score == pytest.approx(100.0)
        assert result.combined_score is not None
        assert result.combined_score >= 90.0
        assert result.event_rating == EventRating.PERFECT


# --- Partial/Missing Data ---

class TestMissingData:
    """Partial and complete data unavailability."""

    def test_no_motion(self) -> None:
        engine = ScoringEngine(_ref(), AppConfig())
        result = engine.score_frame(_pose(500), {"left_elbow": 90.0}, None)
        assert result.motion_score is None
        assert result.timing_score is None
        assert result.combined_score is not None  # pose + angle available

    def test_no_angles(self) -> None:
        engine = ScoringEngine(_ref(), AppConfig())
        result = engine.score_frame(_pose(500), {}, _motion(1.0))
        assert result.angle_score is None
        assert result.combined_score is not None

    def test_no_pose_in_reference(self) -> None:
        ref = ReferenceSequence(
            metadata=VideoMetadata("/t.mp4", 30, 30.0, 1.0, 640, 480),
            poses=tuple(None for _ in range(10)),
            motion_features=tuple(_motion(1.0) for _ in range(10)),
            joint_angles=tuple({"left_elbow": 90.0} for _ in range(10)),
        )
        engine = ScoringEngine(ref, AppConfig())
        result = engine.score_frame(_pose(500), {"left_elbow": 90.0}, _motion(1.0))
        assert result.pose_score is None

    def test_all_unavailable(self) -> None:
        ref = ReferenceSequence(
            metadata=VideoMetadata("/t.mp4", 30, 30.0, 1.0, 640, 480),
            poses=tuple(None for _ in range(10)),
            motion_features=tuple(None for _ in range(10)),
            joint_angles=tuple(None for _ in range(10)),
        )
        engine = ScoringEngine(ref, AppConfig())
        result = engine.score_frame(_pose(500), {}, None)
        assert result.pose_score is None
        assert result.angle_score is None
        assert result.motion_score is None
        assert result.timing_score is None
        assert result.combined_score is None
        assert result.event_rating == EventRating.MISS

    def test_no_artificial_zero_scores(self) -> None:
        """Missing data must remain None, not become 0."""
        engine = ScoringEngine(_ref(), AppConfig())
        result = engine.score_frame(_pose(500), {}, None)
        # motion/timing None, not 0
        assert result.motion_score is None
        assert result.timing_score is None


# --- Sequence ---

class TestSequenceIntegration:
    """score_sequence() behavior."""

    def test_output_length_matches_input(self) -> None:
        engine = ScoringEngine(_ref(), AppConfig())
        poses = [_pose(i * 100) for i in range(7)]
        angles = [{"left_elbow": 90.0} for _ in range(7)]
        motions = [_motion(1.0) for _ in range(7)]
        results = engine.score_sequence(poses, angles, motions)
        assert len(results) == 7

    def test_invalid_pose_produces_none(self) -> None:
        engine = ScoringEngine(_ref(), AppConfig())
        poses: list[NormalizedPose | None] = [_pose(0), None, NormalizedPose.invalid(200)]
        angles: list[dict[str, float | None] | None] = [{}, {}, {}]
        motions: list[MotionFeatures | None] = [None, None, None]
        results = engine.score_sequence(poses, angles, motions)
        assert results[0] is not None
        assert results[1] is None
        assert results[2] is None

    def test_varying_data_availability(self) -> None:
        engine = ScoringEngine(_ref(), AppConfig())
        poses = [_pose(0), _pose(500), _pose(1000)]
        angles: list[dict[str, float | None] | None] = [
            {"left_elbow": 90.0},
            None,
            {"left_elbow": 45.0},
        ]
        motions: list[MotionFeatures | None] = [_motion(1.0), None, _motion(0.5)]
        results = engine.score_sequence(poses, angles, motions)
        assert results[0] is not None
        assert results[0].angle_score is not None
        assert results[1] is not None
        assert results[1].angle_score is None
        assert results[2] is not None


# --- Alignment Integration ---

class TestAlignmentIntegration:
    """Engine uses nearest-frame alignment."""

    def test_first_frame(self) -> None:
        engine = ScoringEngine(_ref(10, 1.0), AppConfig())
        result = engine.score_frame(_pose(ts=0), {"left_elbow": 90.0}, _motion())
        assert result.combined_score is not None

    def test_last_frame(self) -> None:
        engine = ScoringEngine(_ref(10, 1.0), AppConfig())
        result = engine.score_frame(_pose(ts=1000), {"left_elbow": 90.0}, _motion())
        assert result.combined_score is not None

    def test_between_frames(self) -> None:
        engine = ScoringEngine(_ref(10, 1.0), AppConfig())
        result = engine.score_frame(_pose(ts=450), {"left_elbow": 90.0}, _motion())
        assert result.combined_score is not None

    def test_beyond_duration_clamped(self) -> None:
        engine = ScoringEngine(_ref(10, 1.0), AppConfig())
        result = engine.score_frame(_pose(ts=5000), {"left_elbow": 90.0}, _motion())
        assert result.combined_score is not None


# --- Configuration Propagation ---

class TestConfigurationPropagation:
    """Configuration values propagate through the engine."""

    def test_pose_scale_factor(self) -> None:
        """Larger scale → more deduction for same distance."""
        cfg_default = AppConfig()
        cfg_harsh = AppConfig(comparison_config=ComparisonConfig(pose_scale_factor=400.0))
        ref = _ref()

        player = _pose(ts=500, x=0.1)
        angles = {"left_elbow": 90.0}
        motion = _motion(1.0)

        r_default = ScoringEngine(ref, cfg_default).score_frame(player, angles, motion)
        r_harsh = ScoringEngine(ref, cfg_harsh).score_frame(player, angles, motion)

        assert r_default.pose_score is not None
        assert r_harsh.pose_score is not None
        assert r_harsh.pose_score < r_default.pose_score

    def test_angle_scale(self) -> None:
        cfg = AppConfig(comparison_config=ComparisonConfig(angle_scale=2.0))
        engine = ScoringEngine(_ref(), cfg)
        result = engine.score_frame(
            _pose(500), {"left_elbow": 50.0, "right_elbow": -45.0}, _motion()
        )
        # 40° error on left_elbow with scale 2.0 → more deduction
        assert result.angle_score is not None
        assert result.angle_score < 100.0

    def test_min_valid_landmarks(self) -> None:
        """Set min to 34 (more than 33) → always None for pose."""
        cfg = AppConfig(comparison_config=ComparisonConfig(min_valid_landmarks=34))
        engine = ScoringEngine(_ref(), cfg)
        result = engine.score_frame(_pose(500), {}, _motion())
        assert result.pose_score is None

    def test_timing_scale(self) -> None:
        """Higher timing_scale → more penalty for phase mismatch."""
        ref = _ref()
        # Reference has speed=1.0, player has speed=0 → mismatch
        still_motion = _motion(0.0)
        cfg_low = AppConfig(comparison_config=ComparisonConfig(timing_scale=0.1))
        cfg_high = AppConfig(comparison_config=ComparisonConfig(timing_scale=2.0))

        r_low = ScoringEngine(ref, cfg_low).score_frame(_pose(500), {}, still_motion)
        r_high = ScoringEngine(ref, cfg_high).score_frame(_pose(500), {}, still_motion)

        assert r_low.timing_score is not None
        assert r_high.timing_score is not None
        assert r_high.timing_score <= r_low.timing_score

    def test_scoring_thresholds(self) -> None:
        """Custom thresholds change rating classification."""
        cfg = AppConfig(scoring_thresholds=ScoringThresholds(perfect_min=50.0))
        engine = ScoringEngine(_ref(), cfg)
        result = engine.score_frame(
            _pose(500, x=0.15), {"left_elbow": 60.0}, _motion(0.5)
        )
        # With lowered threshold, more likely to get PERFECT
        if result.combined_score is not None and result.combined_score >= 50.0:
            assert result.event_rating == EventRating.PERFECT


# --- Determinism and Immutability ---

class TestDeterminismImmutability:
    """Deterministic results and no input mutation."""

    def test_repeated_calls_identical(self) -> None:
        engine = ScoringEngine(_ref(), AppConfig())
        pose = _pose(333, x=0.05, y=0.02)
        angles = {"left_elbow": 85.0, "right_elbow": -40.0}
        motion = _motion(0.9)

        r1 = engine.score_frame(pose, angles, motion)
        r2 = engine.score_frame(pose, angles, motion)

        assert r1.timestamp_ms == r2.timestamp_ms
        assert r1.pose_score == r2.pose_score
        assert r1.angle_score == r2.angle_score
        assert r1.motion_score == r2.motion_score
        assert r1.timing_score == r2.timing_score
        assert r1.combined_score == r2.combined_score
        assert r1.event_rating == r2.event_rating
        assert r1.feedback == r2.feedback

    def test_sequence_deterministic(self) -> None:
        engine = ScoringEngine(_ref(), AppConfig())
        poses = [_pose(i * 100, x=i * 0.01) for i in range(5)]
        angles = [{"left_elbow": 90.0 - i} for i in range(5)]
        motions = [_motion(1.0) for _ in range(5)]

        s1 = engine.score_sequence(poses, angles, motions)
        s2 = engine.score_sequence(poses, angles, motions)

        for a, b in zip(s1, s2):
            if a is None:
                assert b is None
            else:
                assert b is not None
                assert a.combined_score == b.combined_score

    def test_input_not_mutated(self) -> None:
        engine = ScoringEngine(_ref(), AppConfig())
        pose = _pose(500, x=0.1)
        angles = {"left_elbow": 80.0}
        motion = _motion(0.7)

        pose_copy = copy.deepcopy(pose)
        angles_copy = dict(angles)

        engine.score_frame(pose, angles, motion)

        # Verify inputs unchanged
        assert pose.timestamp_ms == pose_copy.timestamp_ms
        assert pose.landmarks_2d == pose_copy.landmarks_2d
        assert angles == angles_copy
