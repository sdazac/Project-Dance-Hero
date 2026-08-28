# Requirements: Practice Mode Playback Controls (Seek + Speed)

## Introduction

Practice Mode currently supports load, play/pause, and restart. Per `product.md`
(Practice mode "must support ... seek; playback speed control") and the
practice-mode-mvp Requirement 3.5 ("WHEN the video plays at a non-default speed
... the alignment SHALL remain consistent with the displayed playback position"),
Practice Mode must also let the user seek within the reference video and change
playback speed. This spec adds a seek slider and a speed control, wired to the
existing `QMediaPlayer`, while preserving position-based scoring alignment.

Because live scoring aligns via `media_player.position()` (real playback
milliseconds) and computes motion from a rolling pose buffer, seek and speed
changes must keep alignment correct and must not corrupt live motion across a
discontinuity.

## Glossary

- **Seek**: jump playback to an arbitrary position in the reference video.
- **Playback speed / rate**: the `QMediaPlayer` playback rate multiplier
  (1.0 = normal). Slower rates aid learning; faster rates aid review.
- **Position**: current playback time in milliseconds (`media_player.position()`).
- **Duration**: total media length in milliseconds (`media_player.duration()`).
- **Pose buffer**: the bounded rolling buffer of recent normalized player poses
  used for live motion (from the live-full-scoring spec).

## Requirements

### Requirement 1 — Seek within the reference video

**User Story:** As a user practicing a section, I want to jump to any point in the
video, so I can repeat the part I'm learning.

#### Acceptance Criteria

1. WHEN a video is loaded and analyzed THEN the system SHALL display a seek
   control (slider) reflecting the current playback position.
2. WHEN the media position changes during playback THEN the seek slider SHALL
   update to reflect it (without fighting the user while dragging).
3. WHEN the user moves the seek control to a position THEN the system SHALL set
   the media player position to the corresponding time in milliseconds.
4. WHEN the user seeks THEN scoring alignment SHALL immediately use the new
   position (via `media_player.position()`), with no persistent drift.
5. WHEN the user seeks THEN the live pose buffer SHALL be cleared so motion is
   not computed across the discontinuity (a seek is a temporal jump, so
   pre-seek velocity is meaningless afterward).
6. WHEN no video is loaded THEN the seek control SHALL be disabled.

### Requirement 2 — Playback speed control

**User Story:** As a learner, I want to slow down or speed up the video, so I can
practice difficult sections slowly or review quickly.

#### Acceptance Criteria

1. WHEN a video is loaded THEN the system SHALL provide a control to select the
   playback speed from a configurable set of rates.
2. WHEN the user selects a speed THEN the system SHALL call
   `QMediaPlayer.setPlaybackRate` with that rate.
3. WHEN the playback rate is non-default THEN scoring alignment SHALL remain
   consistent with the displayed playback position (position-based alignment
   already reflects the adjusted clock; no additional compensation needed)
   (practice-mode-mvp Req 3.5).
4. WHEN the available speeds are defined THEN they SHALL come from configuration
   (e.g. a `[practice]` `playback_speeds` list and a default speed), not
   hardcoded magic values, and SHALL be validated with a fallback to a sane
   default set.
5. WHEN a speed outside a safe range is configured THEN the loader SHALL fall
   back to defaults (reuse the existing validation/warning pattern).

### Requirement 3 — Controls integrate cleanly with existing behavior

**User Story:** As a user, I want the new controls to fit the existing play/pause
/restart flow without breaking it.

#### Acceptance Criteria

1. WHEN the user pauses THEN the render timer SHALL keep running and scoring SHALL
   stop, unchanged from current behavior.
2. WHEN the user restarts THEN position SHALL reset to 0, the pose buffer SHALL
   clear, and the selected playback speed SHALL be preserved (restart does not
   reset the chosen speed unless the user changes it).
3. WHEN controls are disabled/enabled THEN they SHALL follow the existing
   load→analyze→ready lifecycle (disabled until analysis completes).
4. WHEN the window closes or a camera error occurs THEN cleanup SHALL be
   unchanged (timers stopped, player released) — this spec adds controls only.

### Requirement 4 — Business logic is testable and UI-thin

**User Story:** As a maintainer, I want the seek/speed logic testable without a
real video.

#### Acceptance Criteria

1. WHEN slider values map to/from milliseconds THEN the conversion SHALL be a
   pure, unit-testable helper (slider is integer-ranged; map to duration ms).
2. WHEN speed selection maps a UI choice to a rate THEN it SHALL be derived from
   the configured speed list, testable without Qt.
3. WHEN offscreen widget tests run THEN they SHALL use `QT_QPA_PLATFORM=offscreen`
   with a mocked media player (no real video/audio).

### Requirement 5 — Configuration

**User Story:** As a user on varied hardware/preferences, I want speeds
configurable.

#### Acceptance Criteria

1. WHEN speeds are needed THEN `PracticeConfig` SHALL expose them (e.g.
   `playback_speeds: tuple[float, ...]` and `default_playback_speed: float`).
2. WHEN the `[practice]` config is loaded THEN speeds SHALL be validated (each in
   a safe range, e.g. [0.25, 4.0]; default must be within the list) with fallback
   to defaults on invalid input.
3. WHEN defaults apply THEN they SHALL be sensible for practice (e.g. 0.5, 0.75,
   1.0, 1.25, 1.5; default 1.0).

### Requirement 6 — Non-regression

**User Story:** As a maintainer, I want existing functionality preserved.

#### Acceptance Criteria

1. WHEN this work is complete THEN all existing tests SHALL pass.
2. WHEN inspected THEN existing public APIs (ScoringEngine, PracticeConfig
   existing fields, SessionTracker) SHALL remain backward compatible (config
   additions are additive with defaults).
3. WHEN ruff and mypy run THEN they SHALL report no new errors.
4. WHEN tests run THEN they SHALL NOT require a camera, GPU, or real video.

## Out of Scope

- Frame-by-frame stepping.
- Loop/repeat-section automation (weak-section replay is a later analytics spec).
- Audio pitch correction at non-default speeds (QMediaPlayer default behavior is
  acceptable for the MVP).
