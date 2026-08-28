"""Live current-frame motion extraction for the real-time scoring loop.

During practice the scoring loop only has the most recent player pose, but
velocity (and therefore motion features) requires at least two timestamped
frames. This module maintains no state of its own; instead it accepts a short,
ordered (oldest -> newest) buffer of recent normalized poses and derives motion
features for the current (last) frame.

It deliberately reuses :func:`compute_sequence_motion` rather than
re-implementing any motion math. Running the same sequence function over the
buffer guarantees the live motion matches the reference motion formula exactly
(same central/forward/backward differencing, same units, same thresholds). For
the last element, ``compute_sequence_motion`` uses a backward difference over
frames ``N-2`` and ``N-1``, which is precisely the "velocity up to now" that is
meaningful for live play.
"""

from collections.abc import Sequence

from opendance.config.models import MotionConfig
from opendance.motion.features import compute_sequence_motion
from opendance.motion.motion_result import MotionFeatures
from opendance.motion.normalized_pose import NormalizedPose


def motion_for_latest(
    pose_buffer: Sequence[NormalizedPose],
    config: MotionConfig,
) -> MotionFeatures | None:
    """Compute :class:`MotionFeatures` for the most recent pose in the buffer.

    Runs :func:`compute_sequence_motion` over the buffered poses (ordered
    oldest -> newest) and returns the motion features for the LAST (current)
    pose. Velocity is undefined with a single frame, so fewer than two poses
    yields ``None``.

    Args:
        pose_buffer: Recent normalized player poses, ordered oldest -> newest.
        config: Motion configuration (e.g. ``min_velocity_threshold``).

    Returns:
        Motion features for the current frame, or ``None`` when fewer than two
        poses are available or no result could be computed.
    """
    if len(pose_buffer) < 2:
        return None
    results = compute_sequence_motion(list(pose_buffer), config)
    return results[-1] if results else None
