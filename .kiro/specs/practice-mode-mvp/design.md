# Design: Practice Mode MVP & Real-Time Performance

## Overview

This design makes the live practice loop smooth by separating three rates that
currently compete inside a single 33 ms timer: **render**, **inference**, and
**scoring**. It also fixes temporal correctness (real timestamps instead of a
fixed `+= 33` increment) and preserves the project's original combo/grading
rules (PERFECT/GREAT increase combo; OK/MEH/MISS reset it).

No new architecture, no ML, no GPU. All changes are additive and preserve the
public APIs of Phase 1–3.5.

## Problem Analysis (current behavior)

| Issue | Location | Effect |
|-------|----------|--------|
| Full BGR frame emitted every frame across threads | `FrameWorker.frame_ready` | Large array copies UI↔worker |
| Fixed `timestamp_ms += 33` | `FrameWorker.run` | Drifts from real time; wrong reference alignment |
| Silhouette render + scoring in same 33 ms tick | `PracticeWindow._game_loop_tick` | Render and scoring starve each other |
| No frame dropping | worker → UI signal queue | Stale poses accumulate, movement lags |
| Scoring runs at render rate | `_game_loop_tick` | Unnecessary CPU load ~30/s |

## Architecture: Three Decoupled Rates

```
┌─────────────────────────────────────────────────────────────┐
│ Worker Thread (FrameWorker)                                   │
│   loop: capture → detect → emit latest PoseResult             │
│   rate: INFERENCE (CPU-bound, ~15-16 FPS)                     │
│   timestamp: real monotonic elapsed time                      │
└───────────────┬───────────────────────────────────────────────┘
                │ frame_ready(pose_result)   [latest wins]
                ▼
┌─────────────────────────────────────────────────────────────┐
│ UI Thread (PracticeWindow)                                    │
│   _latest_pose ← most recent pose (overwrites)                │
│                                                               │
│   Render timer (~33ms / 30 FPS): draw silhouette from         │
│                                   _latest_pose                │
│                                                               │
│   Scoring timer (configurable, ~66-100ms / 10-15 FPS):        │
│                  normalize + score + update HUD               │
└─────────────────────────────────────────────────────────────┘
```

The two UI timers are independent. The render timer keeps the silhouette fluid;
the scoring timer runs slower and does the heavy comparison work.

## Components and Changes

### 1. FrameWorker — real timestamps + lighter emission

**File:** `src/opendance/camera/frame_worker.py`

- Replace `self._timestamp_ms += 33` with real elapsed time:
  - Record `start = time.perf_counter()` when the loop begins.
  - `timestamp_ms = int((time.perf_counter() - start) * 1000)`.
  - This guarantees monotonic, real-time timestamps (Requirement 3.2) and keeps
    MediaPipe VIDEO mode happy (must be strictly increasing).
- Keep emitting `frame_ready(frame, pose_result)` for backward compatibility, but
  the UI will only keep the latest (no queue growth). No API change.
- Optional guard: if two consecutive timestamps collide (fast loop), bump by +1 ms
  to preserve strict monotonicity.

### 2. Configuration — scoring rate + render rate

**File:** `src/opendance/config/models.py`, `defaults.toml`, `loader.py`

Add a `PracticeConfig` dataclass (additive, backward-compatible):

```python
@dataclass(frozen=True)
class PracticeConfig:
    """Practice Mode real-time performance settings."""
    render_fps: float = 30.0      # silhouette refresh (visual smoothness)
    scoring_fps: float = 12.0     # how often we score against reference
    silhouette_size: int = 250    # px, square
```

- Add `practice_config` field to `AppConfig`.
- Add `[practice]` section to `defaults.toml`.
- Add validation in `loader.py`: `render_fps` in (1, 120], `scoring_fps` in
  (1, 60], `silhouette_size` in [50, 1000]. Defaults on invalid.
- Rationale: render defaults higher than scoring, per the decoupled-rates
  principle. `scoring_fps=12` keeps meaningful feedback without overloading CPU.

### 3. PracticeWindow — split render and scoring timers

**File:** `src/opendance/ui/practice_window.py`

Replace the single 33 ms `_timer` with two timers:

```python
self._render_timer = QTimer()   # interval = 1000/render_fps
self._render_timer.timeout.connect(self._render_tick)

self._scoring_timer = QTimer()  # interval = 1000/scoring_fps
self._scoring_timer.timeout.connect(self._scoring_tick)
```

- `_render_tick()`:
  - Draw the mirrored silhouette from `self._latest_pose`.
  - Cheap; runs at `render_fps`. Runs even while paused (positioning feedback,
    Requirement 3.3).
- `_scoring_tick()`:
  - Only when playing and engine ready and pose non-empty.
  - Normalize → `dataclasses.replace(timestamp_ms=media_player.position())` →
    `score_frame` → `SessionTracker.update_with_rating` → update HUD.
  - Runs at `scoring_fps`.
- Start/stop both timers together on play/pause; render timer may stay running
  while paused so the user can align their body.

### 4. SessionTracker — restore original combo rules

**File:** `src/opendance/scoring/session_tracker.py`

The current code increments combo on OK. The project's product definition says
OK resets combo. Fix the combo branch to match:

```python
if rating in (EventRating.PERFECT, EventRating.GREAT):
    self.state.combo += 1
    # multiplier bumps stay as-is
else:  # OK, MEH, MISS all reset
    self.state.combo = 0
    self.state.multiplier = 1.0
```

- Grade bands: keep S/A/B/C/D/FAILED per `product.md`. Note the existing tracker
  uses "SS"/"F"; align labels to the documented set where reasonable
  (SS retained as an internal "all-perfect/full-combo" style label only if the
  product doc supports it; otherwise map to S/FAILED). This is a small,
  documented semantic fix, not an algorithm change.
- Preserve accuracy as continuous numerical value (already done).

### 5. Silhouette rendering — keep cheap, render-thread only

**File:** `src/opendance/ui/silhouette_renderer.py`

- No algorithm change needed; it's already a pure function returning a QPixmap.
- Ensure it is only called from `_render_tick` (render rate), not from scoring.
- The `np.ascontiguousarray` + QImage path is retained.

### 6. Diagnostics — expose the three rates

- `PracticeWindow` computes and can display render FPS, inference FPS (from
  `CameraManager.fps` / `FPSMonitor`), and scoring FPS (rolling counter in
  `_scoring_tick`). Shown in the HUD or a small debug label (Requirement 1.5).

## Data Flow (scoring path)

```
media_player.position() (ms, real playback time)
        │
        ▼
_latest_pose (most recent, from worker)
        │
   normalize_pose()
        │
   dataclasses.replace(timestamp_ms = position)
        │
   ScoringEngine.score_frame(pose, {}, None)
        │
   FrameComparison → SessionTracker.update_with_rating
        │
   HUD update (grade, accuracy, combo)
```

Note: player angles/motion are passed as `{}`/`None` for now (pose-only live
scoring), consistent with the current MVP. Angle/motion live scoring is a
possible future enhancement and is out of scope here.

## Configuration Defaults

```toml
[practice]
render_fps = 30.0
scoring_fps = 12.0
silhouette_size = 250
```

## Error Handling

- Camera failure during session → `CameraManager` emits error; PracticeWindow
  stops timers and shows a message (Requirement 7.3).
- Analysis failure → existing `AnalysisWorker.finished` error path retained
  (Requirement 4.6).
- Window close during analysis → terminate worker, stop timers, release player
  and camera (Requirement 7.1, 7.2).
- Empty pose → `_render_tick` draws nothing/last; `_scoring_tick` skips
  (Requirement 2.5).

## Testing Strategy

Unit tests (no camera, no GUI, `QT_QPA_PLATFORM=offscreen` where a widget is
unavoidable):

1. **FrameWorker timestamps** — monotonic increasing, based on elapsed time
   (mock `perf_counter`, mock capture).
2. **SessionTracker combo** — PERFECT→+1, GREAT→+1, OK→reset, MEH→reset,
   MISS→reset; multiplier resets on OK/MEH/MISS.
3. **SessionTracker grading** — boundary accuracy values map to documented bands.
4. **PracticeConfig loading** — defaults, overrides, invalid fallback.
5. **Rate helpers** — interval computation from fps (1000/fps), clamping.

No test requires real hardware; camera/MediaPipe are mocked.

## Non-Goals / Preserved

- No change to PoseDetector, normalize_pose, motion, or scoring formulas.
- No change to ScoringEngine public API.
- No DTW, no ML, no GPU, no networking.
- Subject tracking (Phase 3.5) untouched; live camera uses single-person
  `PoseDetector` as today.

## Traceability

| Requirement | Addressed by |
|-------------|--------------|
| 1 (smooth tracking) | Components 1, 3, 5 (render timer + latest-wins + drop stale) |
| 2 (efficient frames) | Components 1, 3 (latest-wins, reuse detector, decoupled render) |
| 3 (temporal) | Component 1 (real timestamps), Component 3 (position-based scoring) |
| 4 (full flow) | Existing PracticeWindow + Component 3 refinements |
| 5 (combo/grading) | Component 4 (restore original rules) |
| 6 (config) | Component 2 (PracticeConfig) |
| 7 (stability) | Existing closeEvent + Component 3 timer stop |
| 8 (non-regression) | Testing strategy + preserved APIs |
