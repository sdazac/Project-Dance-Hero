# Design: Scoring Accuracy Normalization Fix

## Overview

Separate the two conflated concepts in `SessionTracker`:

- **Arcade score** (`total_score`): points scaled by the combo multiplier.
  Unchanged.
- **Accuracy percentage** (`accuracy_percentage`): a pure, multiplier-independent
  measure of movement quality, defined as the mean per-rating quality weight
  ×100, always in [0, 100].

This is a minimal, focused correctness fix. Combo, multiplier, and arcade-score
math are untouched.

## Root Cause (confirmed)

In `update_with_rating`:

```python
self.state.max_possible_score += max_pts * self.state.multiplier   # pre-bump multiplier
...
if PERFECT/GREAT:
    self.state.multiplier += 0.10 / 0.05                            # bump
pts_gained = BASE_POINTS[rating] * self.state.multiplier            # post-bump multiplier
self.state.total_score += pts_gained
accuracy = total_score / max_possible_score * 100                  # can exceed 100
```

Because the numerator uses the post-bump multiplier and the denominator uses the
pre-bump multiplier, the ratio exceeds 1.0 on PERFECT/GREAT streaks.

## Fix Strategy

Decouple accuracy from the multiplier by computing accuracy from **quality
weights** accumulated per rating, independent of the arcade score.

### Rating quality weights (single source of truth)

Add a class-level constant on `SessionTracker`:

```python
RATING_QUALITY = {
    EventRating.PERFECT: 1.00,
    EventRating.GREAT:   0.75,
    EventRating.OK:      0.50,
    EventRating.MEH:     0.30,
    EventRating.MISS:    0.00,
}
```

Rationale: these correspond to the documented lower bounds of each rating band in
`product.md` (PERFECT 90–100 → 1.0 as the ideal, GREAT ≥75 → 0.75, OK ≥50 →
0.50, MEH ≥30 → 0.30, MISS <30 → 0.0). This makes accuracy explainable: it is the
average "band floor" quality of the user's events.

### State changes

Add two internal accumulators to `SessionState` for the accuracy computation.
To keep the public API stable, we reuse the existing `total_score` /
`max_possible_score` fields for their original arcade meaning and add:

```python
quality_sum: float = 0.0     # sum of RATING_QUALITY[rating] over scored events
rated_events: int = 0        # number of scored events
```

`accuracy_percentage` becomes:

```python
accuracy = (quality_sum / rated_events) * 100.0   if rated_events > 0 else 0.0
```

This is inherently bounded to [0, 100] because each weight is in [0, 1].

Note: adding fields to the `SessionState` dataclass is additive and backward
compatible (the fields have defaults; existing field names/types are unchanged).

### update_with_rating (revised control flow)

```python
def update_with_rating(self, rating):
    # --- Arcade score (unchanged) ---
    max_pts = self.BASE_POINTS[EventRating.PERFECT]
    self.state.max_possible_score += max_pts * self.state.multiplier

    if rating in (PERFECT, GREAT):
        self.state.combo += 1
        self.state.multiplier = min(self.state.multiplier + (0.10 if PERFECT else 0.05), 4.0)
    else:
        self.state.combo = 0
        self.state.multiplier = 1.0

    self.state.total_score += self.BASE_POINTS[rating] * self.state.multiplier

    # --- Accuracy (new, multiplier-independent) ---
    self.state.quality_sum += self.RATING_QUALITY[rating]
    self.state.rated_events += 1
    self.state.accuracy_percentage = (
        (self.state.quality_sum / self.state.rated_events) * 100.0
    )

    self.state.current_grade = self._calculate_grade(self.state.accuracy_percentage)
    return self.state
```

`_calculate_grade` is unchanged; it now always receives a value in [0, 100].

## Why not just clamp?

Clamping `accuracy` to 100 would hide the conceptual error and still make
accuracy depend on combo ordering (e.g., the same set of ratings in different
orders would give different pre-clamp values). The quality-weight mean is
order-independent (Requirement 1.4) and truly bounded, which matches the
"continuous numerical accuracy" intent in `product.md`.

## Data Flow

```
rating ──► RATING_QUALITY[rating] ──► quality_sum, rated_events
                                          │
                                          ▼
                        accuracy = mean(quality) * 100  ∈ [0,100]
                                          │
                                          ▼
                                   _calculate_grade → S/A/B/C/D/FAILED
```

Arcade score path (`multiplier`, `total_score`) runs in parallel and is
unchanged.

## Testing Strategy

Unit tests (pure, no Qt/camera), per the testing steering file:

1. **Bug reproduction / regression**: an all-PERFECT sequence (e.g. 10 events)
   yields `accuracy_percentage == 100.0` (previously >100). This is the
   regression test that reproduces the bug and then passes after the fix.
2. **Bounds**: random/mixed sequences never exceed 100 or drop below 0.
3. **Endpoints**: all-MISS → 0.0; all-PERFECT → 100.0.
4. **Order independence**: the same multiset of ratings in different orders
   yields the same accuracy.
5. **Mean semantics**: known small sequences map to the expected mean×100
   (e.g. [PERFECT, MISS] → 50.0; [GREAT, GREAT] → 75.0; [OK, MEH] → 40.0).
6. **Combo/multiplier/score preserved**: existing combo tests still hold;
   `total_score` still grows with the multiplier; multiplier still caps at 4.0.
7. **Grade at boundaries**: unchanged `_calculate_grade` boundary tests remain
   valid.

Existing tests in `tests/unit/test_session_tracker.py` and the integration test
`tests/integration/test_practice_scoring_path.py` that asserted or tolerated
`accuracy > 100` are updated to assert the corrected bounded behavior.

## Correctness Properties (for property-based tests)

- **P1 (bounded)**: for any finite sequence of ratings, `0.0 <= accuracy <= 100.0`.
- **P2 (order-independent)**: permuting the input ratings does not change the
  final `accuracy_percentage`.
- **P3 (monotone endpoints)**: all-PERFECT ⇒ 100.0; all-MISS ⇒ 0.0.
- **P4 (mean)**: accuracy equals `mean(RATING_QUALITY[r]) * 100` over the inputs.

These are cheap, deterministic properties suitable for Hypothesis.

## Non-Goals / Preserved

- Arcade point values, multiplier curve, rating thresholds, grade bands.
- Public API: `SessionState` existing fields, `update_with_rating`,
  `_calculate_grade` signatures.
- SS / ALL PERFECT / FULL COMBO labels (out of scope).

## Traceability

| Requirement | Addressed by |
|-------------|--------------|
| 1 (bounded, multiplier-independent) | quality-weight mean; P1, P2, P4 |
| 2 (weight mapping) | `RATING_QUALITY` constant |
| 3 (arcade/combo preserved) | unchanged multiplier/score branch |
| 4 (grade boundaries) | unchanged `_calculate_grade`, bounded input |
| 5 (non-regression) | updated tests, unchanged API, ruff/mypy |
