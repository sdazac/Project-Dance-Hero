# OpenDance AI — Testing Strategy

## General rule

Every important algorithm must be independently testable.

Tests should prefer deterministic synthetic data rather than requiring a real camera.

## Unit tests

Unit tests should cover:

* configuration;
* pose normalization;
* landmark transformations;
* joint-angle calculations;
* motion features;
* similarity calculations;
* confidence handling;
* temporal alignment;
* event scoring;
* combo;
* final grading;
* cache identification.

## Scoring boundary tests

Explicitly test:

* 100.00%
* 99.99%
* 90.00%
* 89.99%
* 75.00%
* 74.99%
* 50.00%
* 49.99%
* 30.00%
* 29.99%
* 0.00%

## Grade tests

Test:

* ALL PERFECT;
* FULL COMBO;
* SS;
* SS+;
* S;
* A;
* B;
* C;
* D;
* FAILED.

## Combo tests

Verify:

PERFECT → combo +1

GREAT → combo +1

OK → combo reset

MEH → combo reset

MISS → combo reset

## Pose tests

Test:

* complete pose;
* missing landmarks;
* low-confidence landmarks;
* translated body;
* scaled body;
* rotated body where supported.

## Temporal alignment tests

Create synthetic sequences representing:

* identical timing;
* small delay;
* small advance;
* different movement speed;
* dropped frames;
* missing sections.

The alignment algorithm must not incorrectly make substantially different sequences appear identical.

## Camera tests

Do not require a physical camera for normal unit tests.

Camera hardware tests should be separate integration/manual tests.

## Video tests

Use small synthetic or appropriately licensed test videos.

Do not commit copyrighted commercial videos.

## Regression tests

When an algorithm bug is fixed:

1. reproduce the bug;
2. create a regression test;
3. fix the implementation;
4. ensure the regression test passes.

## Performance tests

As the project matures, measure:

* camera FPS;
* pose inference time;
* reference-video analysis time;
* memory usage;
* cache effectiveness.

Performance tests should not block normal development unless explicitly required.

## Test execution

The project should provide a simple command for running all tests.

The README must document it.

## Definition of done

A feature is not complete when the code merely exists.

A feature is complete when:

* implementation exists;
* relevant tests exist;
* tests pass;
* error cases are considered;
* documentation is updated when necessary.
