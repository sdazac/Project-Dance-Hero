# Design: Practice Mode Playback Controls (Seek + Speed)

## Overview

Add a seek slider and a playback-speed selector to `PracticeWindow`, wired to the
existing `QMediaPlayer`. Because live scoring aligns via `media_player.position()`
(real playback ms) and motion comes from a rolling pose buffer, seek and speed
integrate with minimal, well-contained changes:

- **Speed**: `QMediaPlayer.setPlaybackRate(rate)`. Position-based alignment
  already reflects the adjusted clock, so no scoring compensation is needed
  (practice-mode-mvp Req 3.5).
- **Seek**: `QMediaPlayer.setPosition(ms)`, plus clearing the pose buffer so
  motion is not computed across the temporal discontinuity.

Config gains a configurable speed list. A tiny pure helper handles slider↔ms
mapping for testability.

## Configuration Changes

**File:** `src/opendance/config/models.py`, `defaults.toml`, `loader.py`

Extend `PracticeConfig` (additive, backward compatible):

```python
@dataclass(frozen=True)
class PracticeConfig:
    render_fps: float = 30.0
    scoring_fps: float = 12.0
    silhouette_size: int = 250
    playback_speeds: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5)
    default_playback_speed: float = 1.0
```

`defaults.toml` `[practice]`:

```toml
playback_speeds = [0.5, 0.75, 1.0, 1.25, 1.5]
default_playback_speed = 1.0
```

Loader validation (reuse `validate_value` + warning pattern):
- Parse `playback_speeds` as a list of floats; keep only values in [0.25, 4.0];
  if the resulting list is empty, fall back to the default tuple.
- `default_playback_speed` in [0.25, 4.0]; if not present in the (validated)
  speeds list, fall back to 1.0 if 1.0 is in the list, else the first speed.
- Store as a tuple in the frozen dataclass.

TOML has no tuple type; the loader reads a list and converts to `tuple(...)`.

## UI Changes

**File:** `src/opendance/ui/practice_window.py`

### Seek slider

- Add `self._seek_slider = QSlider(Qt.Orientation.Horizontal)`, range `0..1000`
  (fixed integer resolution; map to ms against duration). Disabled until a media
  source is ready.
- Connect media player signals:
  - `positionChanged(int ms)` → update slider (unless the user is dragging).
  - `durationChanged(int ms)` → store duration; enable slider when > 0.
- Connect slider interaction:
  - `sliderPressed` → set `self._user_seeking = True`.
  - `sliderReleased` → compute target ms from slider value + duration, call
    `_seek_to(ms)`, set `self._user_seeking = False`.
  - (optionally `sliderMoved` to preview, but release-to-seek is simplest/robust)
- `positionChanged` handler skips updating the slider while `self._user_seeking`
  is True (avoid fighting the user).

### `_seek_to(position_ms)`

```python
def _seek_to(self, position_ms: int) -> None:
    self._media_player.setPosition(position_ms)
    # A seek is a temporal jump: discard buffered poses so live motion is not
    # computed across the discontinuity (Requirement 1.5).
    self._pose_buffer.clear()
```

### Speed selector

- Add `self._speed_combo = QComboBox()`, populated from
  `practice_config.playback_speeds` (label e.g. "1.0x"), current index set to
  `default_playback_speed`. Disabled until ready.
- On `currentIndexChanged` / activated → `self._set_playback_speed(rate)`:

```python
def _set_playback_speed(self, rate: float) -> None:
    self._media_player.setPlaybackRate(rate)
```

- Apply `default_playback_speed` to the player when the source becomes ready
  (in `_on_analysis_finished` / `_restart_video`), so playback starts at the
  configured default. Restart preserves the currently selected speed.

### Pure helpers

**File:** `src/opendance/ui/timing.py` (extend) or a small local function.

```python
def slider_to_ms(slider_value: int, slider_max: int, duration_ms: int) -> int:
    """Map an integer slider value in [0, slider_max] to a position in ms."""
    if slider_max <= 0 or duration_ms <= 0:
        return 0
    frac = max(0, min(slider_value, slider_max)) / slider_max
    return int(frac * duration_ms)

def ms_to_slider(position_ms: int, duration_ms: int, slider_max: int) -> int:
    """Map a position in ms to an integer slider value in [0, slider_max]."""
    if duration_ms <= 0 or slider_max <= 0:
        return 0
    frac = max(0, min(position_ms, duration_ms)) / duration_ms
    return int(round(frac * slider_max))
```

Pure and UI-independent → unit-testable (Requirement 4.1).

### Layout

- Add a controls row: seek slider (stretch) above/below the existing button row;
  add the speed combo next to the buttons. Keep the existing button row intact.
- Slider and combo start disabled; enabled in `_on_analysis_finished` alongside
  the existing play/restart enabling.

## Why scoring needs no rate compensation

`_scoring_tick` stamps the player pose with `media_player.position()`. At rate
`r`, wall-clock time `t` maps to media position `≈ r·t` (minus pauses), and the
video frame shown corresponds to that same position. The engine aligns the pose
to the nearest reference frame by that position. So the pose is always compared
to the reference frame actually on screen, regardless of `r`. This is exactly
practice-mode-mvp Req 3.5. Motion velocity uses real inter-tick timestamps
(also position-based), so speed is measured in media-time consistently on both
sides.

The only correctness concern is a seek discontinuity, handled by clearing the
pose buffer.

## Data Flow (additions)

```
QMediaPlayer.durationChanged ─► store duration, enable slider
QMediaPlayer.positionChanged ─► (if not user-seeking) slider = ms_to_slider(pos)
user drags slider ─► on release ─► setPosition(slider_to_ms(value)) + clear buffer
speed combo ─► setPlaybackRate(rate)
```

## Error Handling

- Seek/speed controls disabled until analysis completes and a source is set.
- Duration 0 / not ready → slider disabled, helpers return 0 (no divide-by-zero).
- Seek clears buffer → first post-seek scoring tick has 1 pose → motion None
  (existing safe behavior).

## Testing Strategy

Unit tests (pure): `slider_to_ms` / `ms_to_slider` — endpoints (0, max),
midpoint, clamping out-of-range, zero-duration guard, round-trip approximate
identity.

Config tests: `playback_speeds` / `default_playback_speed` defaults, valid
override (list), invalid entries filtered, empty→default, default not-in-list
fallback.

Offscreen widget tests (mocked media player, `QT_QPA_PLATFORM=offscreen`):
- Slider disabled before ready, enabled after `_on_analysis_finished`.
- `durationChanged` enables the slider and stores duration.
- `positionChanged` updates slider when not seeking; does NOT update while
  `_user_seeking` is True.
- Slider release calls `setPosition` with the mapped ms and clears `_pose_buffer`.
- Speed combo selection calls `setPlaybackRate` with the configured rate.
- `_restart_video` preserves the currently selected speed and clears the buffer.

No camera/GPU/real video required.

## Non-Goals / Preserved

- Play/pause/restart, timers, cleanup, camera-error handling — unchanged.
- Scoring formulas, engine API, session tracker — unchanged.
- Frame stepping, loop/repeat, audio pitch correction — out of scope.

## Traceability

| Requirement | Addressed by |
|-------------|--------------|
| 1 (seek) | seek slider + `_seek_to` + buffer clear |
| 2 (speed) | speed combo + `setPlaybackRate` + config |
| 3 (integration) | enable/disable lifecycle; restart preserves speed |
| 4 (testable) | pure slider↔ms helpers; offscreen tests |
| 5 (config) | PracticeConfig speeds + loader validation |
| 6 (non-regression) | additive config; unchanged APIs; ruff/mypy/tests |
