"""Motion feature extraction using central differences.

Computes per-landmark velocity, acceleration, speed, and direction from a full
sequence of NormalizedPose frames. Uses central differences for interior frames
with forward/backward fallbacks at sequence boundaries.

Units: body-normalized units/sec (velocity), body-normalized units/sec² (acceleration).
Time source: timestamp_ms from each NormalizedPose, converted to seconds.
"""

import math

from opendance.config.models import MotionConfig
from opendance.motion.landmarks import NUM_LANDMARKS
from opendance.motion.motion_result import LandmarkMotion, MotionFeatures
from opendance.motion.normalized_pose import NormalizedPose


def _compute_velocity_for_landmark(
    pos_a: tuple[float, float, float] | None,
    pos_b: tuple[float, float, float] | None,
    dt: float,
    min_velocity_threshold: float,
) -> LandmarkMotion | None:
    """Compute velocity between two positions over time dt.

    Returns None if either position is None or dt is zero.
    Applies min_velocity_threshold: speeds below it are zeroed.
    """
    if pos_a is None or pos_b is None or dt <= 0.0:
        return None

    vx = (pos_b[0] - pos_a[0]) / dt
    vy = (pos_b[1] - pos_a[1]) / dt
    vz = (pos_b[2] - pos_a[2]) / dt

    speed = math.sqrt(vx * vx + vy * vy + vz * vz)

    if speed < min_velocity_threshold:
        return LandmarkMotion(
            velocity_x=0.0,
            velocity_y=0.0,
            velocity_z=0.0,
            speed=0.0,
            acceleration=None,
            direction_x=0.0,
            direction_y=0.0,
            direction_z=0.0,
        )

    dx = vx / speed
    dy = vy / speed
    dz = vz / speed

    return LandmarkMotion(
        velocity_x=vx,
        velocity_y=vy,
        velocity_z=vz,
        speed=speed,
        acceleration=None,  # filled in a second pass
        direction_x=dx,
        direction_y=dy,
        direction_z=dz,
    )


def compute_sequence_motion(
    poses: list[NormalizedPose | None],
    config: MotionConfig | None = None,
) -> list[MotionFeatures | None]:
    """Compute motion features for an entire sequence using central differences.

    For interior frame i (1 <= i <= N-2):
      dt = (poses[i+1].timestamp_ms - poses[i-1].timestamp_ms) / 1000.0
      velocity[i] = (pos[i+1] - pos[i-1]) / dt

    For first frame (i=0): forward difference using frames 0, 1.
      dt = (poses[1].timestamp_ms - poses[0].timestamp_ms) / 1000.0
      velocity[0] = (pos[1] - pos[0]) / dt

    For last frame (i=N-1): backward difference using frames N-2, N-1.
      dt = (poses[N-1].timestamp_ms - poses[N-2].timestamp_ms) / 1000.0
      velocity[N-1] = (pos[N-1] - pos[N-2]) / dt

    Acceleration uses the same central-difference pattern on the speed sequence.

    Returns list of MotionFeatures (same length as input).
    None entries in poses propagate as None in output.

    Args:
        poses: Full sequence of NormalizedPose or None entries.
        config: MotionConfig for min_velocity_threshold. Uses defaults if None.
    """
    if config is None:
        config = MotionConfig()

    n = len(poses)
    if n == 0:
        return []
    if n == 1:
        # Single frame: no velocity possible
        p = poses[0]
        if p is None or not p.valid:
            return [None]
        return [
            MotionFeatures(
                landmark_motions=tuple(None for _ in range(NUM_LANDMARKS)),
                timestamp_ms=p.timestamp_ms,
                dt_seconds=0.0,
            )
        ]

    min_vel = config.min_velocity_threshold

    # First pass: compute velocities using central/forward/backward differences
    velocity_results: list[MotionFeatures | None] = []

    for i in range(n):
        current = poses[i]
        if current is None or not current.valid:
            velocity_results.append(None)
            continue

        # Determine which frames to use for difference
        if i == 0:
            # Forward difference: frames 0 and 1
            next_pose = poses[1] if n > 1 else None
            if next_pose is None or not next_pose.valid:
                velocity_results.append(
                    MotionFeatures(
                        landmark_motions=tuple(None for _ in range(NUM_LANDMARKS)),
                        timestamp_ms=current.timestamp_ms,
                        dt_seconds=0.0,
                    )
                )
                continue
            dt_ms = next_pose.timestamp_ms - current.timestamp_ms
            dt = dt_ms / 1000.0
            pos_a_landmarks = current.landmarks_2d
            pos_b_landmarks = next_pose.landmarks_2d
        elif i == n - 1:
            # Backward difference: frames N-2 and N-1
            prev_pose = poses[n - 2] if n > 1 else None
            if prev_pose is None or not prev_pose.valid:
                velocity_results.append(
                    MotionFeatures(
                        landmark_motions=tuple(None for _ in range(NUM_LANDMARKS)),
                        timestamp_ms=current.timestamp_ms,
                        dt_seconds=0.0,
                    )
                )
                continue
            dt_ms = current.timestamp_ms - prev_pose.timestamp_ms
            dt = dt_ms / 1000.0
            pos_a_landmarks = prev_pose.landmarks_2d
            pos_b_landmarks = current.landmarks_2d
        else:
            # Central difference: frames i-1 and i+1
            prev_pose = poses[i - 1]
            next_pose = poses[i + 1]
            if (
                prev_pose is None
                or not prev_pose.valid
                or next_pose is None
                or not next_pose.valid
            ):
                velocity_results.append(
                    MotionFeatures(
                        landmark_motions=tuple(None for _ in range(NUM_LANDMARKS)),
                        timestamp_ms=current.timestamp_ms,
                        dt_seconds=0.0,
                    )
                )
                continue
            dt_ms = next_pose.timestamp_ms - prev_pose.timestamp_ms
            dt = dt_ms / 1000.0
            pos_a_landmarks = prev_pose.landmarks_2d
            pos_b_landmarks = next_pose.landmarks_2d

        if dt <= 0.0:
            velocity_results.append(
                MotionFeatures(
                    landmark_motions=tuple(None for _ in range(NUM_LANDMARKS)),
                    timestamp_ms=current.timestamp_ms,
                    dt_seconds=0.0,
                )
            )
            continue

        # Compute per-landmark velocity
        motions: list[LandmarkMotion | None] = []
        for lm_idx in range(NUM_LANDMARKS):
            pa = pos_a_landmarks[lm_idx] if lm_idx < len(pos_a_landmarks) else None
            pb = pos_b_landmarks[lm_idx] if lm_idx < len(pos_b_landmarks) else None
            motion = _compute_velocity_for_landmark(pa, pb, dt, min_vel)
            motions.append(motion)

        velocity_results.append(
            MotionFeatures(
                landmark_motions=tuple(motions),
                timestamp_ms=current.timestamp_ms,
                dt_seconds=dt,
            )
        )

    # Second pass: compute acceleration using central differences on speed
    final_results: list[MotionFeatures | None] = []

    for i in range(n):
        mf = velocity_results[i]
        if mf is None or mf.is_empty:
            final_results.append(mf)
            continue

        updated_motions: list[LandmarkMotion | None] = []
        for lm_idx in range(NUM_LANDMARKS):
            lm_motion = mf.landmark_motions[lm_idx]
            if lm_motion is None:
                updated_motions.append(None)
                continue

            # Compute acceleration via central/forward/backward on speed
            accel: float | None = None

            if n >= 3 and 1 <= i <= n - 2:
                # Central difference on speed
                prev_mf = velocity_results[i - 1]
                next_mf = velocity_results[i + 1]
                if (
                    prev_mf is not None
                    and next_mf is not None
                    and prev_mf.landmark_motions[lm_idx] is not None
                    and next_mf.landmark_motions[lm_idx] is not None
                ):
                    prev_speed = prev_mf.landmark_motions[lm_idx].speed  # type: ignore[union-attr]
                    next_speed = next_mf.landmark_motions[lm_idx].speed  # type: ignore[union-attr]
                    if prev_speed is not None and next_speed is not None:
                        prev_ts = poses[i - 1].timestamp_ms if poses[i - 1] else 0  # type: ignore[union-attr]
                        next_ts = poses[i + 1].timestamp_ms if poses[i + 1] else 0  # type: ignore[union-attr]
                        accel_dt = (next_ts - prev_ts) / 1000.0
                        if accel_dt > 0.0:
                            accel = (next_speed - prev_speed) / accel_dt
            elif i == 0 and n >= 2:
                # Forward difference on speed
                next_mf = velocity_results[1]
                if (
                    next_mf is not None
                    and next_mf.landmark_motions[lm_idx] is not None
                ):
                    next_speed = next_mf.landmark_motions[lm_idx].speed  # type: ignore[union-attr]
                    curr_speed = lm_motion.speed
                    if next_speed is not None and curr_speed is not None:
                        accel_dt = mf.dt_seconds
                        if accel_dt > 0.0:
                            accel = (next_speed - curr_speed) / accel_dt
            elif i == n - 1 and n >= 2:
                # Backward difference on speed
                prev_mf = velocity_results[n - 2]
                if (
                    prev_mf is not None
                    and prev_mf.landmark_motions[lm_idx] is not None
                ):
                    prev_speed = prev_mf.landmark_motions[lm_idx].speed  # type: ignore[union-attr]
                    curr_speed = lm_motion.speed
                    if prev_speed is not None and curr_speed is not None:
                        accel_dt = mf.dt_seconds
                        if accel_dt > 0.0:
                            accel = (curr_speed - prev_speed) / accel_dt

            updated_motions.append(
                LandmarkMotion(
                    velocity_x=lm_motion.velocity_x,
                    velocity_y=lm_motion.velocity_y,
                    velocity_z=lm_motion.velocity_z,
                    speed=lm_motion.speed,
                    acceleration=accel,
                    direction_x=lm_motion.direction_x,
                    direction_y=lm_motion.direction_y,
                    direction_z=lm_motion.direction_z,
                )
            )

        final_results.append(
            MotionFeatures(
                landmark_motions=tuple(updated_motions),
                timestamp_ms=mf.timestamp_ms,
                dt_seconds=mf.dt_seconds,
            )
        )

    return final_results
