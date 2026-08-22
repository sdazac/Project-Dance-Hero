"""ScoringEngine: orchestrates the full Phase 3 scoring pipeline.

Thin orchestration layer that composes existing pure functions:
align → compare → aggregate → rate → feedback.
Does not reimplement any comparison formula.
"""

from opendance.config.models import AppConfig
from opendance.motion.motion_result import MotionFeatures
from opendance.motion.normalized_pose import NormalizedPose
from opendance.scoring.aggregation import aggregate_scores
from opendance.scoring.alignment import align_frame
from opendance.scoring.angle_compare import compute_angle_score
from opendance.scoring.feedback import generate_feedback
from opendance.scoring.models import FeedbackItem, FrameComparison
from opendance.scoring.motion_compare import compute_motion_score
from opendance.scoring.pose_compare import compute_pose_score
from opendance.scoring.rating import compute_event_rating
from opendance.scoring.timing_compare import compute_timing_score
from opendance.video.reference_sequence import ReferenceSequence


class ScoringEngine:
    """Orchestrates alignment, comparison, aggregation, rating, and feedback.

    Consumes a precomputed ReferenceSequence and AppConfig.
    Provides per-frame and full-sequence scoring.
    Deterministic: same inputs + config → identical outputs.
    """

    def __init__(self, reference: ReferenceSequence, config: AppConfig) -> None:
        self._reference = reference
        self._config = config
        self._ref_duration_ms = int(reference.metadata.duration_seconds * 1000)
        self._ref_frame_count = len(reference.poses)

    def score_frame(
        self,
        player_pose: NormalizedPose,
        player_angles: dict[str, float | None],
        player_motion: MotionFeatures | None,
    ) -> FrameComparison:
        """Score a single player frame against the aligned reference.

        Pipeline:
        1. Align player timestamp → nearest reference frame.
        2. Retrieve reference pose, angles, motion at that frame.
        3. Compute pose, angle, motion, timing scores.
        4. Aggregate using ScoringWeights.
        5. Classify with ScoringThresholds.
        6. Generate feedback.
        7. Return FrameComparison.
        """
        comp = self._config.comparison_config
        weights = self._config.scoring_weights
        thresholds = self._config.scoring_thresholds
        motion_cfg = self._config.motion_config

        # 1. Align
        ref_idx = align_frame(
            player_pose.timestamp_ms,
            self._ref_duration_ms,
            self._ref_frame_count,
        )

        # 2. Retrieve reference data
        ref_pose = self._reference.poses[ref_idx] if ref_idx < len(self._reference.poses) else None
        ref_angles = (
            self._reference.joint_angles[ref_idx]
            if ref_idx < len(self._reference.joint_angles)
            else None
        )
        ref_motion = (
            self._reference.motion_features[ref_idx]
            if ref_idx < len(self._reference.motion_features)
            else None
        )

        # 3. Compute sub-scores
        pose_score: float | None = None
        angle_score: float | None = None
        motion_score: float | None = None
        timing_score: float | None = None

        if ref_pose is not None and player_pose.valid:
            pose_score = compute_pose_score(
                player_pose,
                ref_pose,
                pose_scale_factor=comp.pose_scale_factor,
                min_valid_landmarks=comp.min_valid_landmarks,
            )

        ref_angles_dict = ref_angles if ref_angles is not None else {}
        if player_angles and ref_angles_dict:
            angle_score = compute_angle_score(
                player_angles,
                ref_angles_dict,
                angle_scale=comp.angle_scale,
            )

        motion_score = compute_motion_score(
            player_motion,
            ref_motion,
            speed_weight=comp.motion_speed_weight,
            direction_weight=comp.motion_direction_weight,
            epsilon=comp.epsilon,
        )

        timing_score = compute_timing_score(
            player_motion,
            ref_motion,
            timing_scale=comp.timing_scale,
            velocity_threshold=motion_cfg.min_velocity_threshold,
        )

        # 4. Aggregate
        combined_score = aggregate_scores(
            pose_score, angle_score, motion_score, timing_score, weights
        )

        # 5. Rate
        event_rating = compute_event_rating(combined_score, thresholds)

        # 6. Feedback
        feedback_items: list[FeedbackItem] = []
        if ref_pose is not None and player_pose.valid:
            feedback_items = generate_feedback(
                player_pose,
                ref_pose,
                player_angles,
                ref_angles_dict,
                significance_threshold=comp.feedback_significance_threshold,
            )

        return FrameComparison(
            timestamp_ms=player_pose.timestamp_ms,
            pose_score=pose_score,
            angle_score=angle_score,
            motion_score=motion_score,
            timing_score=timing_score,
            combined_score=combined_score,
            event_rating=event_rating,
            feedback=tuple(feedback_items),
        )

    def score_sequence(
        self,
        player_poses: list[NormalizedPose | None],
        player_angles_seq: list[dict[str, float | None] | None],
        player_motions: list[MotionFeatures | None],
    ) -> list[FrameComparison | None]:
        """Score an entire player sequence. Returns one comparison per frame.

        None entries in player_poses produce None in output.
        """
        results: list[FrameComparison | None] = []

        for i, pose in enumerate(player_poses):
            if pose is None or not pose.valid:
                results.append(None)
                continue

            angles = player_angles_seq[i] if i < len(player_angles_seq) else None
            motion = player_motions[i] if i < len(player_motions) else None

            comparison = self.score_frame(
                pose,
                angles if angles is not None else {},
                motion,
            )
            results.append(comparison)

        return results
