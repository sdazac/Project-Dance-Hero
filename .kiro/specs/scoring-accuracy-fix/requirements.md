# Requirements: Scoring Accuracy Normalization Fix

## Introduction

`SessionTracker` conflates two distinct concepts: the arcade **score** (points,
scaled by a combo multiplier) and the **accuracy percentage** (a pure measure of
movement quality). Because of this conflation, `accuracy_percentage` can exceed
100% during combo streaks, which violates `product.md` (accuracy bands S:90–100,
and "store continuous numerical accuracy") and produces meaningless grades and
HUD values.

This is a correctness bug in the scoring engine. Per `product.md` product
philosophy, correctness of the movement-analysis engine takes top priority and
must not be sacrificed for game features.

## Bug Condition

The defect manifests when `SessionTracker.update_with_rating` is called with
PERFECT or GREAT ratings that raise the multiplier:

- `max_possible_score` is incremented by `BASE_POINTS[PERFECT] * multiplier`
  using the multiplier value **before** the per-event bump.
- `total_score` is incremented by `BASE_POINTS[rating] * multiplier` using the
  multiplier value **after** the bump (for PERFECT/GREAT).
- Therefore, for high-quality streaks, `total_score / max_possible_score > 1.0`,
  making `accuracy_percentage > 100.0`.

Concretely, a session of consecutive PERFECT ratings yields
`accuracy_percentage` values such as ~106–110%.

## Root Cause

`accuracy_percentage` is derived from multiplier-scaled point totals. The combo
multiplier is a *gamification* device for the arcade score; it must not affect
the *accuracy* measure, which should reflect only the quality of each scored
event relative to the best possible quality.

## Glossary

- **Rating quality weight**: a per-rating value in [0, 1] expressing how good a
  single scored event was (PERFECT = 1.0, MISS = 0.0), independent of combo.
- **Accuracy percentage**: mean rating quality over all scored events, ×100.
  Always in [0, 100].
- **Arcade score**: `total_score`, points scaled by the combo multiplier. May be
  arbitrarily large; used for score display, not accuracy.

## Requirements

### Requirement 1 — Accuracy is bounded and multiplier-independent

**User Story:** As a user, I want my accuracy to be a meaningful percentage in
0–100%, so that my grade reflects how well I actually danced.

#### Acceptance Criteria

1. WHEN any sequence of ratings is processed THEN `accuracy_percentage` SHALL be
   in the closed interval [0.0, 100.0].
2. WHEN only PERFECT ratings are processed THEN `accuracy_percentage` SHALL equal
   100.0 (subject to floating-point tolerance).
3. WHEN only MISS ratings are processed THEN `accuracy_percentage` SHALL equal
   0.0.
4. WHEN a mixed sequence is processed THEN `accuracy_percentage` SHALL equal the
   mean of the per-rating quality weights ×100, and SHALL NOT depend on the
   combo multiplier or the order of ratings.
5. WHEN no ratings have been processed THEN `accuracy_percentage` SHALL be 0.0.

### Requirement 2 — Rating quality weights follow the documented rating bands

**User Story:** As a maintainer, I want per-rating quality to map to the
documented rating semantics, so that accuracy is explainable.

#### Acceptance Criteria

1. WHEN mapping ratings to quality weights THEN the mapping SHALL be:
   PERFECT = 1.0, GREAT = 0.75, OK = 0.50, MEH = 0.30, MISS = 0.0.
2. WHEN the weights are defined THEN they SHALL be derived from / consistent with
   the rating band lower bounds documented in `product.md`
   (PERFECT 90–100, GREAT 75–89.99, OK 50–74.99, MEH 30–49.99, MISS <30).
3. WHEN weights are needed THEN they SHALL be a single source of truth (a
   constant mapping), not duplicated magic numbers.

### Requirement 3 — Arcade score and combo behavior are preserved

**User Story:** As a user, I want my combo and score to keep working as before,
so that only the accuracy bug is fixed.

#### Acceptance Criteria

1. WHEN PERFECT or GREAT ratings occur THEN combo SHALL increase and the
   multiplier SHALL rise exactly as it does today (PERFECT +0.10, GREAT +0.05,
   capped at 4.0).
2. WHEN OK, MEH, or MISS ratings occur THEN combo SHALL reset to 0 and the
   multiplier SHALL reset to 1.0 (unchanged behavior).
3. WHEN ratings are processed THEN `total_score` SHALL remain the
   multiplier-scaled arcade score (its existing formula is unchanged).
4. WHEN the grade is computed THEN it SHALL use the corrected
   `accuracy_percentage` and the documented bands (S/A/B/C/D/FAILED), unchanged
   otherwise.

### Requirement 4 — Grade correctness at boundaries

**User Story:** As a user, I want my final grade to match the documented bands,
so that the result is fair.

#### Acceptance Criteria

1. WHEN accuracy is computed THEN grade band mapping SHALL be S≥90, A≥80, B≥70,
   C≥60, D≥50, FAILED<50 (unchanged), now fed a value guaranteed ≤100.
2. WHEN an all-PERFECT session is graded THEN the grade SHALL be "S" and accuracy
   SHALL be 100.0 (not >100).

### Requirement 5 — Non-regression

**User Story:** As a maintainer, I want existing tests and public APIs preserved.

#### Acceptance Criteria

1. WHEN this fix is complete THEN all existing tests SHALL pass (updated only
   where they asserted the buggy >100% behavior).
2. WHEN the public API is inspected THEN `SessionState` fields and
   `SessionTracker.update_with_rating` / `_calculate_grade` signatures SHALL be
   unchanged.
3. WHEN ruff and mypy run THEN they SHALL report no new errors.

## Out of Scope

- Changing arcade point values or the multiplier curve.
- Changing rating thresholds or grade bands.
- ALL PERFECT / FULL COMBO / SS labels (tracked separately).
