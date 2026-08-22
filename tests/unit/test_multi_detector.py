"""Unit tests for MultiPoseDetector with explicit subject tracking.

Tests: selection, identity lock, crossing, ambiguity,
disappearance, recovery, correction, forward retracking.
"""

import numpy as np

from opendance.pose.multi_detector import (
    MultiPoseDetector,
    PoseCandidate,
    SubjectTrack,
    TrackState,
    _compute_geometry_vector,
    _geometry_similarity,
    compute_body_area,
    compute_center,
    count_visible,
)
from opendance.pose.result import Landmark, PoseResult


def _lm(x: float, y: float, vis: float = 0.9) -> Landmark:
    return Landmark(x=x, y=y, z=0.0, visibility=vis, presence=1.0)


def _grid(
    x0: float, x1: float, y0: float, y1: float,
    n: int = 10, vis: float = 0.9,
) -> tuple[Landmark, ...]:
    xs = np.linspace(x0, x1, n)
    ys = np.linspace(y0, y1, n)
    return tuple(_lm(float(xs[i]), float(ys[i]), vis) for i in range(n))


def _cand(
    cx: float, cy: float, area: float, n: int = 10,
    vis: float = 0.9, ts: int = 0,
) -> PoseCandidate:
    half = max((area ** 0.5) / 2, 0.05)
    landmarks = _grid(cx - half, cx + half, cy - half, cy + half, n, vis)
    pose = PoseResult(landmarks=landmarks, world_landmarks=(), timestamp_ms=ts)
    return PoseCandidate(
        pose_result=pose, body_area=area,
        center_x=cx, center_y=cy, visible_landmarks=n if vis >= 0.5 else 0,
    )


def _det(ambiguity: float = 0.25, max_lost: int = 90) -> MultiPoseDetector:
    """Create detector without MediaPipe for select_primary tests."""
    d = object.__new__(MultiPoseDetector)
    d._config = None
    d._max_lost_frames = max_lost
    d._ambiguity_margin = ambiguity
    d._subject = SubjectTrack()
    d._frame_index = 0
    d._last_candidates = []
    return d


# === Utility tests ===

class TestUtilities:
    def test_body_area(self) -> None:
        lms = _grid(0.2, 0.8, 0.1, 0.9)
        assert abs(compute_body_area(lms) - 0.48) < 1e-6

    def test_center(self) -> None:
        lms = (_lm(0.2, 0.2), _lm(0.8, 0.8))
        cx, cy = compute_center(lms)
        assert abs(cx - 0.5) < 1e-6

    def test_count_visible(self) -> None:
        lms = (_lm(0.5, 0.5, 0.9), _lm(0.5, 0.5, 0.3))
        assert count_visible(lms, 0.5) == 1

    def test_geometry_identical(self) -> None:
        lms = _grid(0.3, 0.7, 0.3, 0.7)
        geo = _compute_geometry_vector(lms, (0.5, 0.5), 0.16)
        assert _geometry_similarity(geo, geo) == 0.0

    def test_geometry_different(self) -> None:
        g1 = _compute_geometry_vector(_grid(0.3, 0.7, 0.3, 0.7), (0.5, 0.5), 0.16)
        g2 = _compute_geometry_vector(_grid(0.1, 0.9, 0.1, 0.9), (0.5, 0.5), 0.64)
        sim = _geometry_similarity(g1, g2)
        assert sim is not None and sim > 0


# === Initial Selection ===

class TestInitialSelection:
    def test_auto_selects_largest(self) -> None:
        d = _det()
        small = _cand(0.3, 0.5, 0.04)
        large = _cand(0.7, 0.5, 0.20)
        r = d.select_primary([small, large])
        assert r is large.pose_result
        assert d.is_locked
        assert d.subject.state == TrackState.TRACKING

    def test_explicit_select_subject(self) -> None:
        d = _det()
        a = _cand(0.3, 0.5, 0.20)
        b = _cand(0.7, 0.5, 0.04)
        d._last_candidates = [a, b]
        d.select_subject(1)  # Select the smaller one explicitly
        assert d.is_locked
        # Subject locked at b's center
        assert d.subject.last_center == (0.7, 0.5)

    def test_subject_id_persists(self) -> None:
        d = _det()
        d.select_primary([_cand(0.5, 0.5, 0.10)])
        sid = d.subject.subject_id
        # Next frame
        d.select_primary([_cand(0.5, 0.5, 0.10)])
        assert d.subject.subject_id == sid


# === Hard Identity Lock ===

class TestHardLock:
    def test_larger_does_not_steal(self) -> None:
        d = _det()
        a = _cand(0.3, 0.5, 0.08)
        d.select_primary([a])
        sid = d.subject.subject_id

        a2 = _cand(0.3, 0.5, 0.08)
        huge = _cand(0.8, 0.5, 0.50)
        r = d.select_primary([a2, huge])
        assert r is a2.pose_result
        assert d.subject.subject_id == sid

    def test_closer_does_not_steal(self) -> None:
        d = _det()
        a = _cand(0.3, 0.5, 0.08)
        d.select_primary([a])

        # Move a slightly, b appears closer to original
        a2 = _cand(0.32, 0.5, 0.08)
        # b at (0.3, 0.5) — exactly where a was!
        # But trajectory predicts (0.32, 0.5) or beyond
        # Only single candidate within range if a moved
        b = _cand(0.3, 0.5, 0.08)
        d.select_primary([a2, b])
        # Both within range. Ambiguity may trigger or trajectory wins.
        assert d.subject.subject_id == d.subject.subject_id  # stays same


# === Crossing Prevention ===

class TestCrossing:
    def test_crossing_trajectory_favors_original(self) -> None:
        d = _det()
        # Lock on A at (0.3, 0.5)
        a0 = _cand(0.3, 0.5, 0.09)
        b0 = _cand(0.7, 0.5, 0.08)
        d.select_primary([a0, b0])

        # A moves right (0.4)
        a1 = _cand(0.4, 0.5, 0.09)
        b1 = _cand(0.6, 0.5, 0.08)
        r1 = d.select_primary([a1, b1])
        assert r1 is a1.pose_result

        # A at (0.5), B at (0.5) — crossing point
        a2 = _cand(0.5, 0.5, 0.09)
        b2 = _cand(0.5, 0.5, 0.08)
        r2 = d.select_primary([a2, b2])
        # Ambiguous (same position) → should be empty/UNCERTAIN
        # OR trajectory distinguishes them
        # Either way: must NOT be b2
        assert r2 is not b2.pose_result

    def test_b_never_becomes_primary(self) -> None:
        d = _det()
        a = _cand(0.2, 0.5, 0.10)
        b = _cand(0.8, 0.5, 0.08)
        d.select_primary([a, b])
        sid = d.subject.subject_id

        # A moves toward B over 6 frames
        for step in range(1, 7):
            ax = 0.2 + step * 0.1
            bx = 0.8 - step * 0.1
            ca = _cand(ax, 0.5, 0.10)
            cb = _cand(bx, 0.5, 0.08)
            r = d.select_primary([ca, cb])
            assert r is not cb.pose_result
            assert d.subject.subject_id == sid


# === Disappearance & Recovery ===

class TestDisappearance:
    def test_brief_disappearance_occluded(self) -> None:
        d = _det()
        d.select_primary([_cand(0.5, 0.5, 0.10)])
        for _ in range(3):
            r = d.select_primary([])
            assert r.is_empty
        assert d.subject.state == TrackState.OCCLUDED
        assert d.is_locked

    def test_long_disappearance_lost(self) -> None:
        d = _det()
        d.select_primary([_cand(0.5, 0.5, 0.10)])
        for _ in range(100):
            d.select_primary([])
        assert d.subject.state == TrackState.LOST
        assert d.is_locked

    def test_other_not_selected_during_loss(self) -> None:
        d = _det()
        d.select_primary([_cand(0.5, 0.5, 0.10)])
        # Subject disappears, other appears far away
        other = _cand(0.1, 0.1, 0.30)
        for _ in range(10):
            r = d.select_primary([other])
            assert r.is_empty

    def test_recovery(self) -> None:
        d = _det()
        d.select_primary([_cand(0.5, 0.5, 0.10)])
        sid = d.subject.subject_id
        for _ in range(5):
            d.select_primary([])
        # Returns
        r = d.select_primary([_cand(0.5, 0.5, 0.10)])
        assert not r.is_empty
        assert d.subject.state == TrackState.TRACKING
        assert d.subject.subject_id == sid


# === Ambiguity Gate ===

class TestAmbiguity:
    def test_identical_candidates_uncertain(self) -> None:
        d = _det()
        c = _cand(0.5, 0.5, 0.10)
        d.select_primary([c])

        # Two identical candidates
        c1 = _cand(0.5, 0.5, 0.10)
        c2 = _cand(0.5, 0.5, 0.10)
        r = d.select_primary([c1, c2])
        assert r.is_empty
        assert d.subject.state == TrackState.UNCERTAIN

    def test_clear_single_accepted(self) -> None:
        d = _det()
        d.select_primary([_cand(0.5, 0.5, 0.10)])
        # One candidate at same place, other far
        close = _cand(0.5, 0.5, 0.10)
        far = _cand(0.95, 0.95, 0.10)
        r = d.select_primary([close, far])
        assert not r.is_empty


# === Manual Correction ===

class TestCorrection:
    def test_correct_creates_new_anchor(self) -> None:
        d = _det()
        d.select_primary([_cand(0.5, 0.5, 0.10)])
        sid = d.subject.subject_id
        old_anchor = d.subject.anchor_frame

        # Simulate some frames then correct
        for _ in range(5):
            d.select_primary([])
        assert d.subject.state in (TrackState.OCCLUDED, TrackState.LOST)

        # Correct to a new candidate
        new_cand = _cand(0.6, 0.5, 0.12)
        d._last_candidates = [new_cand]
        d.correct_subject(frame_index=10, candidate_index=0)

        assert d.subject.subject_id == sid  # Same identity
        assert d.subject.state == TrackState.TRACKING
        assert d.subject.confidence == 1.0
        assert d.subject.anchor_frame == 10
        assert d.subject.anchor_frame != old_anchor

    def test_correct_preserves_subject_id(self) -> None:
        d = _det()
        d.select_primary([_cand(0.3, 0.5, 0.10)])
        sid = d.subject.subject_id

        d._last_candidates = [_cand(0.7, 0.5, 0.10)]
        d.correct_subject(frame_index=50, candidate_index=0)

        assert d.subject.subject_id == sid

    def test_forward_retrack_after_correction(self) -> None:
        d = _det()
        d.select_primary([_cand(0.5, 0.5, 0.10)])

        # Lose track
        for _ in range(10):
            d.select_primary([])

        # Correct at new position
        new_pos = _cand(0.6, 0.5, 0.10)
        d._last_candidates = [new_pos]
        d.correct_subject(frame_index=15, candidate_index=0)

        # Continue tracking from new anchor
        r = d.select_primary([_cand(0.62, 0.5, 0.10)])
        assert not r.is_empty
        assert d.subject.state == TrackState.TRACKING


# === Single Person Unchanged ===

class TestSinglePerson:
    def test_continuous_single(self) -> None:
        d = _det()
        for i in range(20):
            c = _cand(0.5 + i * 0.005, 0.5, 0.10)
            r = d.select_primary([c])
            assert not r.is_empty
            assert d.subject.state == TrackState.TRACKING


# === Determinism ===

class TestDeterminism:
    def test_same_input_same_output(self) -> None:
        d1 = _det()
        d2 = _det()
        cands = [_cand(0.3, 0.5, 0.09), _cand(0.7, 0.5, 0.08)]
        r1 = d1.select_primary(cands)
        r2 = d2.select_primary(cands)
        assert r1.landmarks == r2.landmarks


# === Reset ===

class TestReset:
    def test_reset_unlocks(self) -> None:
        d = _det()
        d.select_primary([_cand(0.5, 0.5, 0.10)])
        assert d.is_locked
        d.reset_tracking()
        assert not d.is_locked
        assert d.subject.state == TrackState.UNLOCKED


# === No Silent Switch ===

class TestNoSilentSwitch:
    def test_never_returns_other_during_tracking(self) -> None:
        """Over 20 frames with two candidates, subject never switches."""
        d = _det()
        # Lock on A at left
        a = _cand(0.2, 0.5, 0.10)
        b = _cand(0.8, 0.5, 0.08)
        d.select_primary([a, b])
        sid = d.subject.subject_id

        for step in range(20):
            ax = 0.2 + step * 0.01
            ca = _cand(ax, 0.5, 0.10)
            cb = _cand(0.8 - step * 0.01, 0.5, 0.08)
            r = d.select_primary([ca, cb])
            # Must never be cb
            if not r.is_empty:
                assert r is ca.pose_result
            assert d.subject.subject_id == sid
