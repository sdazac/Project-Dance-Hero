"""Unit tests for signed 2D joint angle calculation.

Tests compute_joint_angles() with known geometric configurations:
- 0 degrees (collinear, same direction)
- +90 degrees (counterclockwise right angle)
- -90 degrees (clockwise right angle)
- 180 / -180 degrees (collinear, opposite direction)
- Missing landmark → None
- Degenerate (zero-length vector) → None
- All defined joint names present in output
- Deterministic repeated computation
"""

import pytest

from opendance.motion.angles import compute_joint_angles
from opendance.motion.landmarks import (
    JOINT_ANGLES,
    LEFT_ELBOW,
    LEFT_SHOULDER,
    LEFT_WRIST,
    NUM_LANDMARKS,
)
from opendance.motion.normalized_pose import NormalizedPose


def _make_pose_with_landmarks(
    landmarks_2d: list[tuple[float, float, float] | None],
) -> NormalizedPose:
    """Helper to construct a NormalizedPose with specific 2D landmarks."""
    return NormalizedPose(
        timestamp_ms=0,
        landmarks_2d=tuple(landmarks_2d),
        landmarks_3d=None,
        visibilities=tuple(1.0 for _ in range(len(landmarks_2d))),
        presences=tuple(1.0 for _ in range(len(landmarks_2d))),
        body_center=(0.0, 0.0, 0.0),
        body_scale=1.0,
        valid=True,
    )


def _pose_with_left_elbow_config(
    shoulder: tuple[float, float, float],
    elbow: tuple[float, float, float],
    wrist: tuple[float, float, float],
) -> NormalizedPose:
    """Create a NormalizedPose with specific left elbow configuration.

    left_elbow joint = (LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST)
    proximal=shoulder, joint_center=elbow, distal=wrist
    """
    lm = [(0.0, 0.0, 0.0)] * NUM_LANDMARKS
    lm_list: list[tuple[float, float, float] | None] = list(lm)  # type: ignore[arg-type]
    lm_list[LEFT_SHOULDER] = shoulder
    lm_list[LEFT_ELBOW] = elbow
    lm_list[LEFT_WRIST] = wrist
    return _make_pose_with_landmarks(lm_list)


class TestAngleZeroDegrees:
    """Collinear points, same direction → 0 degrees."""

    def test_zero_angle_horizontal(self) -> None:
        """Shoulder-Elbow-Wrist all along positive x → 0 degrees."""
        # BA = shoulder - elbow = (-1, 0) ; BC = wrist - elbow = (1, 0)
        # cross = (-1)*0 - 0*1 = 0 ; dot = (-1)*1 + 0*0 = -1
        # atan2(0, -1) = pi → 180 degrees (NOT 0)
        # For 0 degrees, both vectors must point same direction:
        # shoulder at (2,0), elbow at (1,0), wrist at (0,0)
        # BA = (2-1, 0) = (1,0) ; BC = (0-1, 0) = (-1,0)
        # cross = 1*0 - 0*(-1) = 0 ; dot = 1*(-1) + 0 = -1 → 180
        # Actually 0 degrees means BA and BC point the SAME direction:
        # shoulder at (0,0), elbow at (1,0), wrist at (2,0)
        # BA = (0-1,0-0) = (-1,0) ; BC = (2-1,0-0) = (1,0)
        # cross = (-1)*0 - 0*1 = 0 ; dot = (-1)*1 + 0*0 = -1 → atan2(0,-1) = 180
        # For true 0 degrees: BA parallel to BC same direction:
        # shoulder at (2,0), elbow at (1,0), wrist at (0,0)
        # BA = (1,0) ; BC = (-1,0) → still 180
        # 0 degrees happens when vectors point same direction from joint:
        # shoulder at (0,1), elbow at (0,0), wrist at (0,-1)
        # BA = (0,1) ; BC = (0,-1) → cross=0*(-1)-1*0=0 ; dot=0+(-1)=-1 → 180
        # For 0 degrees: vectors must be same direction:
        # shoulder at (0,1), elbow at (0,0), wrist at (0,1)
        # BA = (0,1) ; BC = (0,1) → cross=0*1-1*0=0 ; dot=0+1=1 → atan2(0,1)=0
        pose = _pose_with_left_elbow_config(
            shoulder=(0.0, 1.0, 0.0),
            elbow=(0.0, 0.0, 0.0),
            wrist=(0.0, 1.0, 0.0),
        )
        angles = compute_joint_angles(pose)
        assert angles["left_elbow"] == pytest.approx(0.0)


class TestAnglePlus90:
    """Counterclockwise right angle → +90 degrees."""

    def test_positive_90(self) -> None:
        """BA = (1,0), BC = (0,1) → cross=1*1-0*0=1; dot=0 → atan2(1,0)=90."""
        pose = _pose_with_left_elbow_config(
            shoulder=(1.0, 0.0, 0.0),
            elbow=(0.0, 0.0, 0.0),
            wrist=(0.0, 1.0, 0.0),
        )
        angles = compute_joint_angles(pose)
        assert angles["left_elbow"] == pytest.approx(90.0)


class TestAngleMinus90:
    """Clockwise right angle → -90 degrees."""

    def test_negative_90(self) -> None:
        """BA = (1,0), BC = (0,-1) → cross=1*(-1)-0*0=-1; dot=0 → atan2(-1,0)=-90."""
        pose = _pose_with_left_elbow_config(
            shoulder=(1.0, 0.0, 0.0),
            elbow=(0.0, 0.0, 0.0),
            wrist=(0.0, -1.0, 0.0),
        )
        angles = compute_joint_angles(pose)
        assert angles["left_elbow"] == pytest.approx(-90.0)


class TestAngle180:
    """Collinear, opposite direction → ±180 degrees."""

    def test_180_degrees(self) -> None:
        """BA = (1,0), BC = (-1,0) → cross=0; dot=-1 → atan2(0,-1)=180."""
        pose = _pose_with_left_elbow_config(
            shoulder=(1.0, 0.0, 0.0),
            elbow=(0.0, 0.0, 0.0),
            wrist=(-1.0, 0.0, 0.0),
        )
        angles = compute_joint_angles(pose)
        assert angles["left_elbow"] == pytest.approx(180.0)


class TestMissingLandmark:
    """Missing landmark produces None."""

    def test_none_proximal(self) -> None:
        lm: list[tuple[float, float, float] | None] = [(0.0, 0.0, 0.0)] * NUM_LANDMARKS
        lm[LEFT_SHOULDER] = None  # proximal missing
        lm[LEFT_ELBOW] = (0.0, 0.0, 0.0)
        lm[LEFT_WRIST] = (1.0, 0.0, 0.0)
        pose = _make_pose_with_landmarks(lm)
        angles = compute_joint_angles(pose)
        assert angles["left_elbow"] is None

    def test_none_joint_center(self) -> None:
        lm: list[tuple[float, float, float] | None] = [(0.0, 0.0, 0.0)] * NUM_LANDMARKS
        lm[LEFT_SHOULDER] = (1.0, 0.0, 0.0)
        lm[LEFT_ELBOW] = None  # joint center missing
        lm[LEFT_WRIST] = (0.0, 1.0, 0.0)
        pose = _make_pose_with_landmarks(lm)
        angles = compute_joint_angles(pose)
        assert angles["left_elbow"] is None

    def test_none_distal(self) -> None:
        lm: list[tuple[float, float, float] | None] = [(0.0, 0.0, 0.0)] * NUM_LANDMARKS
        lm[LEFT_SHOULDER] = (1.0, 0.0, 0.0)
        lm[LEFT_ELBOW] = (0.0, 0.0, 0.0)
        lm[LEFT_WRIST] = None  # distal missing
        pose = _make_pose_with_landmarks(lm)
        angles = compute_joint_angles(pose)
        assert angles["left_elbow"] is None


class TestDegenerateVector:
    """Zero-length vector produces None."""

    def test_proximal_at_joint(self) -> None:
        """Proximal same position as joint → BA = (0,0) → degenerate."""
        pose = _pose_with_left_elbow_config(
            shoulder=(0.0, 0.0, 0.0),  # same as elbow
            elbow=(0.0, 0.0, 0.0),
            wrist=(1.0, 0.0, 0.0),
        )
        angles = compute_joint_angles(pose)
        assert angles["left_elbow"] is None

    def test_distal_at_joint(self) -> None:
        """Distal same position as joint → BC = (0,0) → degenerate."""
        pose = _pose_with_left_elbow_config(
            shoulder=(1.0, 0.0, 0.0),
            elbow=(0.0, 0.0, 0.0),
            wrist=(0.0, 0.0, 0.0),  # same as elbow
        )
        angles = compute_joint_angles(pose)
        assert angles["left_elbow"] is None


class TestAllJointNamesPresent:
    """All defined joint names appear in the output dict."""

    def test_all_joints_present(self) -> None:
        lm: list[tuple[float, float, float] | None] = [
            (float(i) * 0.1, float(i) * 0.05, 0.0) for i in range(NUM_LANDMARKS)
        ]
        pose = _make_pose_with_landmarks(lm)
        angles = compute_joint_angles(pose)

        for joint_name in JOINT_ANGLES:
            assert joint_name in angles


class TestDeterminism:
    """Repeated computation produces identical results."""

    def test_deterministic(self) -> None:
        pose = _pose_with_left_elbow_config(
            shoulder=(1.0, 1.0, 0.0),
            elbow=(0.0, 0.0, 0.0),
            wrist=(1.0, -1.0, 0.0),
        )
        a1 = compute_joint_angles(pose)
        a2 = compute_joint_angles(pose)
        assert a1 == a2


class TestAngleRange:
    """Output is always in [-180, 180]."""

    def test_various_angles_in_range(self) -> None:
        """Several configurations all produce angles within [-180, 180]."""
        configs = [
            ((1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            ((0.0, 1.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
            ((1.0, 1.0, 0.0), (0.0, 0.0, 0.0), (-1.0, -1.0, 0.0)),
            ((-1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, -1.0, 0.0)),
        ]
        for shoulder, elbow, wrist in configs:
            pose = _pose_with_left_elbow_config(shoulder, elbow, wrist)
            angles = compute_joint_angles(pose)
            angle = angles["left_elbow"]
            assert angle is not None
            assert -180.0 <= angle <= 180.0
