"""Offscreen integration test for the Practice Mode scoring path (task 8.1).

Drives a few ``PracticeWindow._scoring_tick`` calls with mocked camera/player
and asserts that the HUD values (grade, accuracy, combo) update through the
REAL scoring path: ``_scoring_tick`` -> real ``SessionTracker.update_with_rating``
-> real ``ScoreBoardWidget.update_score``. Also asserts temporal alignment: the
pose handed to ``score_frame`` carries ``timestamp_ms == media_player.position()``.

Approach chosen
---------------
- **Scoring engine**: a lightweight *recording fake* engine that returns a
  deterministic ``FrameComparison`` with a chosen ``event_rating``. This keeps
  the ratings deterministic (so we can prove combo build/reset semantics) while
  still exercising the genuine ``SessionTracker`` and ``ScoreBoardWidget`` and
  the genuine ``_scoring_tick`` orchestration. The fake also records the pose it
  is given so we can assert the ``media_player.position()`` alignment. The real
  ``ScoringEngine`` is unit-tested elsewhere; here the intent is the HUD/session
  integration and playback-position alignment (Requirements 3.1, 4.4, 4.5).
- **normalize_pose**: patched at ``opendance.ui.practice_window.normalize_pose``
  to return a known-valid ``NormalizedPose`` (``valid=True``) so the tick
  proceeds past the validity guard without needing a heavy real landmark set.
  ``dataclasses.replace(..., timestamp_ms=position())`` is still exercised on the
  real object, which is the behavior under test for alignment.

Validates: Requirements 3.1, 4.4, 4.5
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication

from opendance.config import load_config
from opendance.config.models import AppConfig
from opendance.motion.landmarks import NUM_LANDMARKS
from opendance.motion.normalized_pose import NormalizedPose
from opendance.scoring.models import EventRating, FrameComparison
from opendance.ui.practice_window import PracticeWindow

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """Ensure a single QApplication exists for the widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture()
def app_config() -> AppConfig:
    """Real AppConfig via load_config so all sections/defaults are present."""
    return load_config()


def _make_camera_manager() -> MagicMock:
    """MagicMock CameraManager safe for PracticeWindow.__init__.

    ``frame_worker`` is None so the frame_ready connection is skipped and no
    real camera is opened. ``fps`` returns a float for the debug overlay.
    """
    manager = MagicMock()
    manager.frame_worker = None
    manager.fps = 0.0
    return manager


class _NonEmptyPose:
    """Minimal stand-in for a detected pose (is_empty is False).

    ``_scoring_tick`` only checks ``is_empty`` on the raw pose before handing it
    to the (patched) ``normalize_pose``, so no real landmark data is required.
    """

    is_empty = False


def _valid_normalized_pose(timestamp_ms: int = 0) -> NormalizedPose:
    """Build a NON-empty, valid NormalizedPose (valid=True).

    Only ``valid`` and ``timestamp_ms`` matter for the path under test; the
    landmark tuples are filled with harmless placeholder values.
    """
    coords = tuple((0.0, 0.0, 0.0) for _ in range(NUM_LANDMARKS))
    ones = tuple(1.0 for _ in range(NUM_LANDMARKS))
    return NormalizedPose(
        timestamp_ms=timestamp_ms,
        landmarks_2d=coords,
        landmarks_3d=coords,
        visibilities=ones,
        presences=ones,
        body_center=(0.0, 0.0, 0.0),
        body_scale=1.0,
        valid=True,
    )


class _RecordingEngine:
    """Deterministic scoring engine that records the pose it scores.

    Returns a ``FrameComparison`` with a scripted ``event_rating`` per call,
    exercising the real SessionTracker/ScoreBoardWidget through ``_scoring_tick``.
    """

    def __init__(self, ratings: list[EventRating]) -> None:
        self._ratings = list(ratings)
        self._index = 0
        self.scored_timestamps: list[int] = []
        self.scored_poses: list[NormalizedPose] = []

    def score_frame(
        self,
        player_pose: NormalizedPose,
        player_angles: dict[str, float | None],
        player_motion: object | None,
    ) -> FrameComparison:
        rating = self._ratings[min(self._index, len(self._ratings) - 1)]
        self._index += 1
        self.scored_poses.append(player_pose)
        self.scored_timestamps.append(player_pose.timestamp_ms)
        return FrameComparison(
            timestamp_ms=player_pose.timestamp_ms,
            pose_score=None,
            angle_score=None,
            motion_score=None,
            timing_score=None,
            combined_score=None,
            event_rating=rating,
            feedback=(),
        )


@pytest.fixture()
def window(qapp: QApplication, app_config: AppConfig) -> PracticeWindow:
    """PracticeWindow with mocked camera and a mocked media player.

    The real ``QMediaPlayer`` is replaced with a MagicMock so ``position()`` is
    controllable and no real media pipeline is exercised. A live pose is
    provided so ``_scoring_tick`` proceeds to the scoring branch.
    """
    win = PracticeWindow(_make_camera_manager(), app_config)
    mock_player = MagicMock()
    mock_player.playbackState.return_value = QMediaPlayer.PlaybackState.StoppedState
    mock_player.position.return_value = 0
    win._media_player = mock_player
    win._is_playing = True
    win._latest_pose = _NonEmptyPose()  # type: ignore[assignment]
    return win


def _drive_tick(
    window: PracticeWindow, monkeypatch: pytest.MonkeyPatch, position_ms: int
) -> None:
    """Set the playback position and drive one _scoring_tick with valid pose."""
    window._media_player.position.return_value = position_ms
    monkeypatch.setattr(
        "opendance.ui.practice_window.normalize_pose",
        lambda pose, cfg: _valid_normalized_pose(),
    )
    window._scoring_tick()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAlignmentUsesPlaybackPosition:
    """The scored pose timestamp equals media_player.position() (Req 3.1)."""

    def test_scored_pose_uses_current_position(
        self, window: PracticeWindow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = _RecordingEngine([EventRating.PERFECT])
        window._scoring_engine = engine  # type: ignore[assignment]

        _drive_tick(window, monkeypatch, position_ms=1234)

        assert engine.scored_timestamps == [1234]
        assert engine.scored_poses[0].timestamp_ms == 1234

    def test_alignment_follows_changing_position(
        self, window: PracticeWindow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = _RecordingEngine([EventRating.PERFECT, EventRating.PERFECT])
        window._scoring_engine = engine  # type: ignore[assignment]

        _drive_tick(window, monkeypatch, position_ms=500)
        _drive_tick(window, monkeypatch, position_ms=1750)

        # The second scored pose must reflect the NEW playback position, proving
        # alignment reads media_player.position() on each tick.
        assert engine.scored_timestamps == [500, 1750]


class TestHudUpdatesThroughScoringPath:
    """Grade/accuracy/combo update via the real session + scoreboard (Req 4.4)."""

    def test_combo_builds_on_consecutive_perfects(
        self, window: PracticeWindow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = _RecordingEngine([EventRating.PERFECT, EventRating.PERFECT])
        window._scoring_engine = engine  # type: ignore[assignment]

        _drive_tick(window, monkeypatch, position_ms=100)
        _drive_tick(window, monkeypatch, position_ms=200)

        # Session state built by real SessionTracker: two PERFECTs build combo.
        assert window._session.state.combo == 2
        # Accuracy is the multiplier-independent mean of per-rating quality
        # weights, so two PERFECTs yield exactly 100.0 (mean quality 1.0),
        # which maps to the top "S" grade band.
        assert window._session.state.accuracy_percentage == pytest.approx(100.0)
        assert window._session.state.current_grade == "S"

        # Scoreboard reflects the session state (readable label text).
        assert window._scoreboard.combo_label.text() == "2x"
        assert window._scoreboard.grade_label.text() == "S"
        expected_acc = f"{window._session.state.accuracy_percentage:.1f}%"
        assert window._scoreboard.acc_label.text() == expected_acc

    def test_ok_rating_resets_combo(
        self, window: PracticeWindow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = _RecordingEngine(
            [EventRating.PERFECT, EventRating.PERFECT, EventRating.OK]
        )
        window._scoring_engine = engine  # type: ignore[assignment]

        _drive_tick(window, monkeypatch, position_ms=100)
        _drive_tick(window, monkeypatch, position_ms=200)
        assert window._session.state.combo == 2

        # A resetting rating (OK) drives combo back to 0 through the same path.
        _drive_tick(window, monkeypatch, position_ms=300)
        assert window._session.state.combo == 0
        assert window._scoreboard.combo_label.text() == "0x"

    def test_miss_rating_resets_combo(
        self, window: PracticeWindow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engine = _RecordingEngine([EventRating.GREAT, EventRating.MISS])
        window._scoring_engine = engine  # type: ignore[assignment]

        _drive_tick(window, monkeypatch, position_ms=100)
        assert window._session.state.combo == 1

        _drive_tick(window, monkeypatch, position_ms=200)
        assert window._session.state.combo == 0
        assert window._scoreboard.combo_label.text() == "0x"


class TestRealEngineIntegration:
    """A REAL ScoringEngine also drives the HUD end-to-end (Req 3.1, 4.4)."""

    def test_real_engine_updates_hud(
        self, window: PracticeWindow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Build a minimal synthetic ReferenceSequence and a real ScoringEngine
        # to prove the genuine scoring path produces a rating and updates the HUD.
        from opendance.scoring.engine import ScoringEngine
        from opendance.video.reference_sequence import (
            ReferenceSequence,
            VideoMetadata,
        )

        ref_poses = tuple(
            _valid_normalized_pose(timestamp_ms=i * 100) for i in range(3)
        )
        reference = ReferenceSequence(
            metadata=VideoMetadata(
                file_path="synthetic.mp4",
                total_frames=3,
                fps=10.0,
                duration_seconds=0.3,
                width=640,
                height=480,
            ),
            poses=ref_poses,
            motion_features=(None, None, None),
            joint_angles=(None, None, None),
        )
        window._scoring_engine = ScoringEngine(reference, window._app_config)

        # Drive a couple of ticks; the real engine computes a real rating and the
        # HUD must update (grade text is a valid grade band, combo is an int).
        _drive_tick(window, monkeypatch, position_ms=0)
        _drive_tick(window, monkeypatch, position_ms=200)

        # Session accuracy is now the multiplier-independent quality mean, so it
        # is always bounded to [0, 100], and the grade is a valid band.
        assert 0.0 <= window._session.state.accuracy_percentage <= 100.0
        assert window._scoreboard.grade_label.text() in {
            "SS",
            "S",
            "A",
            "B",
            "C",
            "D",
            "FAILED",
        }
        # Accuracy label always reflects the session's numeric accuracy.
        expected = f"{window._session.state.accuracy_percentage:.1f}%"
        assert window._scoreboard.acc_label.text() == expected


# ---------------------------------------------------------------------------
# live-full-scoring task 4 — all four metrics live (real engine, full pipeline)
# ---------------------------------------------------------------------------


def _distinct_normalized_pose(
    timestamp_ms: int = 0, offset: float = 0.0
) -> NormalizedPose:
    """Build a valid NormalizedPose with all landmarks at distinct coords.

    Unlike ``_valid_normalized_pose`` (which uses all-zero coords, giving
    degenerate joint triplets and no motion), this places every landmark at a
    unique 2D position so ``compute_joint_angles`` yields non-None signed angles
    and consecutive frames produce non-zero displacement for motion. ``offset``
    shifts every landmark so successive reference frames actually move.
    """
    landmarks_2d: tuple[tuple[float, float, float] | None, ...] = tuple(
        (float(i) * 0.05 + offset, float(i * i) * 0.01 + offset, 0.0)
        for i in range(NUM_LANDMARKS)
    )
    return NormalizedPose(
        timestamp_ms=timestamp_ms,
        landmarks_2d=landmarks_2d,
        landmarks_3d=None,
        visibilities=tuple(1.0 for _ in range(NUM_LANDMARKS)),
        presences=tuple(1.0 for _ in range(NUM_LANDMARKS)),
        body_center=(0.0, 0.0, 0.0),
        body_scale=1.0,
        valid=True,
    )


class _RecordingScoreFrame:
    """Wraps a real ScoringEngine.score_frame, recording each FrameComparison.

    Delegates to the genuine ``score_frame`` (so the full align → compare →
    aggregate → rate pipeline runs) and stores every returned ``FrameComparison``
    so the test can assert on the sub-scores actually produced live.
    """

    def __init__(self, real_score_frame: object) -> None:
        self._real = real_score_frame
        self.results: list[FrameComparison] = []

    def __call__(
        self,
        player_pose: NormalizedPose,
        player_angles: dict[str, float | None],
        player_motion: object | None,
    ) -> FrameComparison:
        comparison = self._real(player_pose, player_angles, player_motion)  # type: ignore[operator]
        self.results.append(comparison)
        return comparison


class TestAllFourMetricsLive:
    """A real ScoringEngine fed by _scoring_tick produces non-None angle AND
    motion sub-scores once the reference carries angle + motion data and the
    player buffer has ≥2 poses.

    Validates: Requirements 1.3, 2.3
    """

    def test_angle_and_motion_scores_are_live(
        self, window: PracticeWindow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from opendance.config.models import MotionConfig
        from opendance.motion.angles import compute_joint_angles
        from opendance.motion.features import compute_sequence_motion
        from opendance.scoring.engine import ScoringEngine
        from opendance.video.reference_sequence import (
            ReferenceSequence,
            VideoMetadata,
        )

        # Reference poses that MOVE frame-to-frame (distinct offsets) so both
        # joint angles and motion features are well defined for the reference.
        ref_poses = tuple(
            _distinct_normalized_pose(timestamp_ms=i * 100, offset=i * 0.02)
            for i in range(3)
        )
        ref_angles = tuple(compute_joint_angles(pose) for pose in ref_poses)
        ref_motion = tuple(
            compute_sequence_motion(list(ref_poses), MotionConfig())
        )

        reference = ReferenceSequence(
            metadata=VideoMetadata(
                file_path="synthetic.mp4",
                total_frames=3,
                fps=10.0,
                # Duration comfortably covers the driven positions (0, 100 ms).
                duration_seconds=0.3,
                width=640,
                height=480,
            ),
            poses=ref_poses,
            motion_features=ref_motion,
            joint_angles=ref_angles,
        )

        engine = ScoringEngine(reference, window._app_config)
        # Wrap the real score_frame so we can inspect the produced comparisons
        # while still driving the genuine pipeline through _scoring_tick.
        recorder = _RecordingScoreFrame(engine.score_frame)
        engine.score_frame = recorder  # type: ignore[method-assign, assignment]
        window._scoring_engine = engine  # type: ignore[assignment]

        # Player poses: distinct landmark coords so player angles are non-None
        # (NOTE: not _drive_tick, which patches normalize_pose to the all-zero
        # _valid_normalized_pose whose degenerate triplets give None angles).
        monkeypatch.setattr(
            "opendance.ui.practice_window.normalize_pose",
            lambda pose, cfg: _distinct_normalized_pose(),
        )

        # Two ticks at distinct positions within the reference duration: the
        # first buffers a single pose (motion None), the second yields motion.
        window._media_player.position.return_value = 0
        window._scoring_tick()
        window._media_player.position.return_value = 100
        window._scoring_tick()

        assert len(recorder.results) == 2
        last = recorder.results[-1]

        # Angle metric is live: reference has angles, player angles non-empty.
        assert last.angle_score is not None
        # Motion metric is live: reference has motion, player motion non-None
        # after two buffered poses with a real elapsed dt.
        assert last.motion_score is not None
        # Aggregate is well formed and bounded.
        assert last.combined_score is not None
        assert 0.0 <= last.combined_score <= 100.0
