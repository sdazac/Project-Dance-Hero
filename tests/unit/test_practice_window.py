"""Unit tests for PracticeWindow timer wiring, tick guards, and cleanup.

Covers optional tasks 5.5 (timer wiring / tick guards) and 7.3 (cleanup and
error handling). All tests run under ``QT_QPA_PLATFORM=offscreen`` with a fully
mocked ``CameraManager`` and a mocked ``QMediaPlayer`` so no real camera is
opened and no real video/audio pipeline is exercised.

Validates: Requirements 1.6, 2.5, 3.3, 6.4 (task 5.5)
Validates: Requirements 7.1, 7.2, 7.3 (task 7.3)
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication

from opendance.camera.state import CameraState
from opendance.config import load_config
from opendance.config.models import AppConfig
from opendance.motion.landmarks import NUM_LANDMARKS
from opendance.motion.motion_result import MotionFeatures
from opendance.motion.normalized_pose import NormalizedPose
from opendance.pose.result import PoseResult
from opendance.ui.practice_window import PracticeWindow
from opendance.ui.timing import fps_to_interval_ms


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """Ensure a single QApplication exists for the widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture()
def app_config() -> AppConfig:
    """Real AppConfig so practice_config defaults (30/12/250) are present."""
    return load_config()


def _make_camera_manager() -> MagicMock:
    """Build a MagicMock CameraManager safe for PracticeWindow.__init__.

    ``start()`` is a no-op mock (no real camera). ``frame_worker`` is None so the
    ``frame_ready`` connection is skipped. ``state_changed.connect`` is a mock
    call. ``fps`` returns a float for the debug overlay.
    """
    manager = MagicMock()
    manager.frame_worker = None
    manager.fps = 0.0
    return manager


@pytest.fixture()
def window(qapp: QApplication, app_config: AppConfig) -> PracticeWindow:
    """Construct a PracticeWindow with mocked camera and mocked media player.

    The real ``QMediaPlayer`` created in ``__init__`` is replaced with a
    MagicMock after construction so play/pause/stop are deterministic and no
    real media source is required. A reference is kept via the fixture return so
    the widget is not garbage-collected mid-test.
    """
    camera_manager = _make_camera_manager()
    win = PracticeWindow(camera_manager, app_config)
    # Replace the real media player with a deterministic mock. Default playback
    # state is StoppedState so _toggle_playback takes the play branch unless a
    # test overrides it.
    mock_player = MagicMock()
    mock_player.playbackState.return_value = QMediaPlayer.PlaybackState.StoppedState
    win._media_player = mock_player
    return win


# ---------------------------------------------------------------------------
# Task 5.5 — timer wiring and tick guards
# ---------------------------------------------------------------------------


class TestTimerWiring:
    """Render/scoring timers exist with config-derived intervals (Req 1.6, 6.4)."""

    def test_timers_are_qtimers(self, window: PracticeWindow) -> None:
        assert isinstance(window._render_timer, QTimer)
        assert isinstance(window._scoring_timer, QTimer)

    def test_render_interval_from_config(
        self, window: PracticeWindow, app_config: AppConfig
    ) -> None:
        expected = fps_to_interval_ms(app_config.practice_config.render_fps)
        assert window._render_timer.interval() == expected
        assert expected == 33  # 30 fps default

    def test_scoring_interval_from_config(
        self, window: PracticeWindow, app_config: AppConfig
    ) -> None:
        expected = fps_to_interval_ms(app_config.practice_config.scoring_fps)
        assert window._scoring_timer.interval() == expected
        assert expected == 83  # 12 fps default


class TestPlayPauseTimers:
    """Both timers start on play; only scoring stops on pause (Req 3.3)."""

    def test_both_timers_start_on_play(self, window: PracticeWindow) -> None:
        window._restart_video()
        assert window._render_timer.isActive()
        assert window._scoring_timer.isActive()
        assert window._is_playing is True

    def test_pause_stops_scoring_keeps_render(self, window: PracticeWindow) -> None:
        # Start playing first.
        window._restart_video()
        assert window._render_timer.isActive()
        assert window._scoring_timer.isActive()

        # Force the pause branch: media player reports PlayingState.
        window._media_player.playbackState.return_value = (
            QMediaPlayer.PlaybackState.PlayingState
        )
        window._toggle_playback()

        # Scoring stops, render keeps running (positioning feedback).
        assert window._scoring_timer.isActive() is False
        assert window._render_timer.isActive() is True
        assert window._is_playing is False


class TestScoringTickGuards:
    """_scoring_tick skips scoring when paused or pose is empty (Req 2.5, 3.3)."""

    def test_no_scoring_when_paused(self, window: PracticeWindow) -> None:
        engine = MagicMock()
        window._scoring_engine = engine
        window._is_playing = False
        window._latest_pose = _NonEmptyPose()

        window._scoring_tick()

        engine.score_frame.assert_not_called()

    def test_no_scoring_when_pose_none(self, window: PracticeWindow) -> None:
        engine = MagicMock()
        window._scoring_engine = engine
        window._is_playing = True
        window._latest_pose = None

        window._scoring_tick()

        engine.score_frame.assert_not_called()

    def test_no_scoring_when_pose_empty(self, window: PracticeWindow) -> None:
        engine = MagicMock()
        window._scoring_engine = engine
        window._is_playing = True
        window._latest_pose = PoseResult.empty()

        window._scoring_tick()

        engine.score_frame.assert_not_called()


class TestRenderTickWhilePaused:
    """_render_tick still draws the silhouette while paused (Req 3.3)."""

    def test_render_runs_while_paused(self, window: PracticeWindow) -> None:
        window._is_playing = False
        window._latest_pose = _NonEmptyPose()

        pixmap = QPixmap(10, 10)
        with patch(
            "opendance.ui.practice_window.get_transparent_silhouette",
            return_value=pixmap,
        ) as mock_silhouette:
            window._render_tick()

        mock_silhouette.assert_called_once()

    def test_render_skips_empty_pose(self, window: PracticeWindow) -> None:
        window._is_playing = False
        window._latest_pose = PoseResult.empty()

        with patch(
            "opendance.ui.practice_window.get_transparent_silhouette",
        ) as mock_silhouette:
            window._render_tick()

        mock_silhouette.assert_not_called()


# ---------------------------------------------------------------------------
# Task 7.3 — cleanup and error handling
# ---------------------------------------------------------------------------


class TestCloseEventCleanup:
    """closeEvent stops timers, stops player, terminates worker (Req 7.1, 7.2)."""

    def test_close_event_full_cleanup(self, window: PracticeWindow) -> None:
        worker = MagicMock()
        worker.isRunning.return_value = True
        window._worker = worker

        window._render_timer.start()
        window._scoring_timer.start()
        assert window._render_timer.isActive()
        assert window._scoring_timer.isActive()

        window.closeEvent(QCloseEvent())

        assert window._render_timer.isActive() is False
        assert window._scoring_timer.isActive() is False
        window._media_player.stop.assert_called_once()
        window._camera_manager.stop.assert_called_once()
        worker.terminate.assert_called_once()
        worker.wait.assert_called_once()

    def test_close_event_without_running_worker(
        self, window: PracticeWindow
    ) -> None:
        worker = MagicMock()
        worker.isRunning.return_value = False
        window._worker = worker

        window._render_timer.start()
        window._scoring_timer.start()

        window.closeEvent(QCloseEvent())

        assert window._render_timer.isActive() is False
        assert window._scoring_timer.isActive() is False
        window._media_player.stop.assert_called_once()
        worker.terminate.assert_not_called()


class TestCameraErrorHandling:
    """Camera error stops the loop safely; non-error states are ignored (Req 7.3)."""

    def test_error_state_stops_timers(self, window: PracticeWindow) -> None:
        window._render_timer.start()
        window._scoring_timer.start()
        window._is_playing = True

        window._on_camera_state_changed(CameraState.ERROR, "boom")

        assert window._render_timer.isActive() is False
        assert window._scoring_timer.isActive() is False
        assert window._is_playing is False
        window._media_player.stop.assert_called_once()
        assert "boom" in window._loading_overlay.text()

    def test_non_error_state_does_nothing(self, window: PracticeWindow) -> None:
        window._render_timer.start()
        window._scoring_timer.start()
        window._is_playing = True

        window._on_camera_state_changed(CameraState.ACTIVE, "")

        # Prior timer state is untouched and playback continues.
        assert window._render_timer.isActive() is True
        assert window._scoring_timer.isActive() is True
        assert window._is_playing is True
        window._media_player.stop.assert_not_called()


class _NonEmptyPose:
    """Minimal stand-in for a detected pose (is_empty is False).

    Used where _scoring_tick / _render_tick only check ``is_empty`` before the
    guarded branch; scoring beyond the guard is prevented by mocking the engine
    or is short-circuited earlier, so no real landmark data is required.
    """

    is_empty = False


# ---------------------------------------------------------------------------
# live-full-scoring task 2.3 — angles + motion wiring into _scoring_tick
# ---------------------------------------------------------------------------


def _make_valid_normalized_pose(timestamp_ms: int = 0) -> NormalizedPose:
    """Build a valid NormalizedPose with all 33 landmarks at distinct coords.

    Coordinates are spread so that every joint-angle triplet
    (proximal, joint_center, distal) is non-degenerate — the two arms of the
    angle point in different directions, so ``compute_joint_angles`` yields at
    least one non-None signed angle. The exact positions are irrelevant to the
    wiring under test; they only need to be present and non-collinear per joint.
    """
    # Distinct 2D coords per landmark. Using (i, i*i) guarantees no two points
    # coincide and that consecutive triplets are not collinear, so joint angles
    # are well defined and non-degenerate.
    landmarks_2d: tuple[tuple[float, float, float] | None, ...] = tuple(
        (float(i) * 0.05, float(i * i) * 0.01, 0.0) for i in range(NUM_LANDMARKS)
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


class _SpyScoringEngine:
    """Records the arguments passed to ``score_frame`` for assertions.

    Stands in for a real ``ScoringEngine`` in the wiring tests: it does not
    score anything, it just captures ``player_angles`` and ``player_motion`` so
    the test can verify what ``_scoring_tick`` fed into the engine.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[object, object, object]] = []
        self.last_angles: object = None
        self.last_motion: object = None

    def score_frame(
        self, player_pose: object, player_angles: object, player_motion: object
    ) -> None:
        self.calls.append((player_pose, player_angles, player_motion))
        self.last_angles = player_angles
        self.last_motion = player_motion
        # Return None so _scoring_tick skips the session/scoreboard update path.
        return None


class TestLiveScoringInputs:
    """_scoring_tick feeds real angles + buffered motion to score_frame.

    Validates: Requirements 1.2, 2.3, 2.4, 2.5
    """

    def _prepare(
        self,
        window: PracticeWindow,
        monkeypatch: pytest.MonkeyPatch,
    ) -> _SpyScoringEngine:
        """Wire a valid pose, a spy engine, and a stubbed normalize_pose.

        ``normalize_pose`` is patched to return a fresh valid NormalizedPose so
        the tick reaches the angle/motion computation with real landmark data
        (no camera, no MediaPipe). ``_scoring_tick`` then stamps the timestamp
        from ``media_player.position()`` via ``dataclasses.replace``.
        """
        monkeypatch.setattr(
            "opendance.ui.practice_window.normalize_pose",
            lambda pose, cfg: _make_valid_normalized_pose(),
        )
        spy = _SpyScoringEngine()
        window._scoring_engine = spy  # type: ignore[assignment]
        window._is_playing = True
        window._latest_pose = _NonEmptyPose()  # type: ignore[assignment]
        window._media_player.position.return_value = 0
        return spy

    def test_angles_dict_is_non_empty(
        self, window: PracticeWindow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Req 1.2: player angles computed from the pose are passed (not {}).
        spy = self._prepare(window, monkeypatch)

        window._scoring_tick()

        assert spy.calls, "score_frame was never called"
        angles = spy.last_angles
        assert isinstance(angles, dict)
        assert len(angles) > 0
        assert any(value is not None for value in angles.values())

    def test_first_tick_passes_motion_none(
        self, window: PracticeWindow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Req 2.4: with a single buffered pose, motion is undefined -> None.
        spy = self._prepare(window, monkeypatch)

        window._scoring_tick()

        assert len(window._pose_buffer) == 1
        assert spy.last_motion is None

    def test_second_tick_passes_motion_features(
        self, window: PracticeWindow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Req 2.3: with two poses at distinct timestamps, motion is available.
        spy = self._prepare(window, monkeypatch)

        window._media_player.position.return_value = 0
        window._scoring_tick()
        # Advance the playback clock so the second pose has a later timestamp
        # (non-zero dt => real velocity, not the dt<=0 None-motion guard).
        window._media_player.position.return_value = 100
        window._scoring_tick()

        assert len(window._pose_buffer) == 2
        assert isinstance(spy.last_motion, MotionFeatures)

    def test_buffer_is_bounded(
        self, window: PracticeWindow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Req 2.5: buffer never grows past its maxlen (5) across many ticks.
        self._prepare(window, monkeypatch)

        for i in range(8):
            window._media_player.position.return_value = i * 100
            window._scoring_tick()

        assert len(window._pose_buffer) == 5

    def test_buffer_cleared_on_restart(
        self, window: PracticeWindow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Req 2.5: a new session starts with a clean motion history.
        self._prepare(window, monkeypatch)

        for i in range(3):
            window._media_player.position.return_value = i * 100
            window._scoring_tick()
        assert len(window._pose_buffer) > 0

        # _restart_video uses the mock media player (setPosition/play are mocks)
        # and does not itself call _scoring_tick, so the buffer stays empty.
        window._restart_video()

        assert len(window._pose_buffer) == 0
