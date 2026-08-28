# Implementation Plan: Scoring Accuracy Normalization Fix

## Overview

Fix the `SessionTracker` accuracy bug where `accuracy_percentage` can exceed 100%
during PERFECT/GREAT combo streaks. Decouple accuracy (multiplier-independent
quality mean, bounded [0,100]) from the arcade score (multiplier-scaled points,
unchanged). Follows the bug-condition methodology: reproduce first, then fix.

The design defines formal Correctness Properties (P1–P4), so property-based tests
are included alongside unit tests.

## Tasks

- [x] 1. Write bug condition exploration property test
  - Write a Hypothesis property test asserting that for any sequence of ratings,
    `SessionTracker` yields `0.0 <= accuracy_percentage <= 100.0` (Property P1).
    Place it in `tests/unit/test_session_tracker_accuracy.py`. On the CURRENT
    (unfixed) code this test is EXPECTED TO FAIL for PERFECT/GREAT streaks
    (accuracy > 100), confirming the bug exists.
  - _Requirements: 1.1_

- [x] 2. Implement the accuracy normalization fix
  - [x] 2.1 Add rating quality weights and accuracy accumulators
    - In `src/opendance/scoring/session_tracker.py`, add a class constant
      `RATING_QUALITY` mapping PERFECT=1.00, GREAT=0.75, OK=0.50, MEH=0.30,
      MISS=0.00 (single source of truth).
    - Add `quality_sum: float = 0.0` and `rated_events: int = 0` fields to
      `SessionState` (additive, defaults preserve backward compatibility).
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 2.2 Compute accuracy from the quality mean, independent of multiplier
    - In `update_with_rating`, accumulate `quality_sum += RATING_QUALITY[rating]`
      and `rated_events += 1`, then set
      `accuracy_percentage = (quality_sum / rated_events) * 100.0` when
      `rated_events > 0`, else 0.0.
    - Leave the arcade-score path (`max_possible_score`, `total_score`,
      `combo`, `multiplier`) exactly as-is.
    - Keep `_calculate_grade` unchanged; it now receives a value in [0,100].
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 3.2, 3.3, 4.1, 4.2_

- [x] 3. Checkpoint - reproduce-then-pass
  - Re-run the task 1 exploration test; it MUST now pass (accuracy bounded).
    Ensure the fix turns the previously failing property green.

- [x]* 4. Write unit and property tests for corrected accuracy
  - [x]* 4.1 Endpoint and mean-semantics unit tests
    - all-PERFECT (10 events) → 100.0; all-MISS → 0.0; [PERFECT, MISS] → 50.0;
      [GREAT, GREAT] → 75.0; [OK, MEH] → 40.0; empty → 0.0.
    - _Requirements: 1.2, 1.3, 1.5, 2.1_

  - [x]* 4.2 Property tests P2/P3/P4
    - P2 order-independence: permuted rating multiset → same accuracy.
    - P3 endpoints: all-PERFECT → 100.0, all-MISS → 0.0.
    - P4 mean: accuracy == mean(RATING_QUALITY[r]) * 100 over inputs.
    - _Requirements: 1.2, 1.3, 1.4_

  - [x]* 4.3 Preserve combo/multiplier/score regression tests
    - Assert combo increments (PERFECT/GREAT) and resets (OK/MEH/MISS),
      multiplier +0.10/+0.05 and 4.0 cap, and `total_score` still grows with the
      multiplier (arcade path unchanged).
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 5. Update existing tests that assumed >100% behavior
  - In `tests/unit/test_session_tracker.py` and
    `tests/integration/test_practice_scoring_path.py`, update any assertion that
    tolerated `accuracy > 100` (e.g. the all-PERFECT "S" test) to assert the
    corrected bounded value (all-PERFECT → 100.0, grade "S").
  - _Requirements: 4.2, 5.1_

- [x] 6. Final checkpoint - full verification
  - Run the full suite (`QT_QPA_PLATFORM=offscreen pytest tests/`), ruff, and
    mypy. Confirm no regressions, public API unchanged, all green.
  - _Requirements: 5.1, 5.2, 5.3_

## Notes

- Tasks marked `*` are optional additional test tasks; task 1 (exploration) and
  task 5 (test updates) are required because they encode the bug contract.
- Property-based tests use Hypothesis (already a project dependency).
- No hardware required; SessionTracker is pure.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["3"] },
    { "id": 4, "tasks": ["4.1", "4.2", "4.3", "5"] },
    { "id": 5, "tasks": ["6"] }
  ]
}
```
