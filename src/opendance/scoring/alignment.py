"""Temporal alignment: nearest-frame mapping from player timestamp to reference.

Maps a player timestamp to the nearest reference frame index using
timestamp-ratio calculation. No landmark interpolation. No DTW.
Deterministic and stateless.
"""


def align_frame(
    player_timestamp_ms: int,
    reference_duration_ms: int,
    reference_frame_count: int,
) -> int:
    """Map player timestamp to nearest reference frame index.

    Formula:
        ratio = clamp(player_timestamp_ms / reference_duration_ms, 0.0, 1.0)
        exact_index = ratio * (reference_frame_count - 1)
        frame_index = round(exact_index)
        return clamp(frame_index, 0, reference_frame_count - 1)

    Args:
        player_timestamp_ms: Player's current frame timestamp in milliseconds.
        reference_duration_ms: Total reference sequence duration in milliseconds.
        reference_frame_count: Number of frames in the reference sequence.

    Returns:
        Nearest reference frame index, clamped to [0, reference_frame_count - 1].
        Returns 0 if reference_frame_count <= 1 or reference_duration_ms <= 0.
    """
    if reference_frame_count <= 0:
        return 0
    if reference_frame_count == 1:
        return 0
    if reference_duration_ms <= 0:
        return 0

    # Clamp ratio to [0, 1]
    ratio = max(0.0, min(1.0, player_timestamp_ms / reference_duration_ms))

    # Compute exact position and round to nearest frame
    exact_index = ratio * (reference_frame_count - 1)
    frame_index = round(exact_index)

    # Clamp to valid range
    return max(0, min(frame_index, reference_frame_count - 1))
