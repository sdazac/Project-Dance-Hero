# OpenDance AI — Coding Standards

## General principles

Write clear, maintainable Python.

Prioritize:

1. correctness;
2. readability;
3. testability;
4. performance;
5. simplicity.

Do not optimize prematurely.

## Python

Use Python 3.x.

Use type hints for:

* public functions;
* methods;
* important internal data structures.

Prefer explicit types over ambiguous dictionaries when a domain object is important.

Use dataclasses when appropriate.

## Naming

Use:

* snake_case for variables and functions;
* PascalCase for classes;
* UPPER_CASE for constants.

Names should describe their purpose.

Avoid generic names such as:

* data;
* temp;
* obj;
* thing;
* result2.

unless their scope is extremely limited.

## Functions

Prefer small functions with one clear responsibility.

Avoid functions that simultaneously:

* read video;
* perform pose detection;
* calculate scoring;
* update UI.

Separate those responsibilities.

## Classes

Classes should have a clear responsibility.

Avoid large "god classes".

Do not create abstractions merely for the sake of abstraction.

## UI

PySide6 widgets should primarily handle:

* user interaction;
* displaying information;
* triggering application actions.

Core business logic must remain outside widgets.

## Error handling

Handle expected failures explicitly.

Examples:

* camera unavailable;
* unsupported video;
* corrupted video;
* pose model unavailable;
* insufficient body visibility;
* invalid configuration.

Errors shown to users should be understandable.

Technical details should be logged.

Do not silently ignore errors.

## Logging

Use the application logging system.

Do not use print statements as the primary production logging mechanism.

Do not log:

* raw camera frames;
* sensitive personal data;
* unnecessary user media information.

## Dependencies

Do not introduce a dependency unless:

1. it solves a real requirement;
2. it is maintained;
3. it is compatible with the project;
4. the benefit justifies the added complexity.

Reuse existing dependencies whenever possible.

## Performance

Avoid unnecessary copies of video frames.

Avoid unnecessary conversions between image formats.

Avoid repeatedly initializing MediaPipe models.

Reuse initialized inference resources when safe.

Avoid blocking the UI thread.

## Configuration

Do not hardcode:

* scoring thresholds;
* scoring weights;
* camera resolution;
* FPS assumptions;
* playback speeds.

Put configurable values in the configuration system.

## Comments

Comments should explain why something is necessary, not simply repeat what the code does.

Avoid excessive comments.

Document algorithms that are mathematically non-obvious.

## Testing

Every important algorithm must have unit tests.

Especially test:

* pose normalization;
* angle calculation;
* similarity;
* temporal alignment;
* scoring;
* combo;
* final grades.

Boundary conditions must be tested.

## Refactoring

Do not perform broad refactors during unrelated feature work.

If a refactor is necessary:

1. explain why;
2. keep it focused;
3. test it;
4. avoid mixing it with unrelated features.

## Git

Use focused commits.

Prefer commit messages such as:

feat: add camera pose detection

fix: handle missing pose landmarks

test: add scoring boundary tests

refactor: separate pose normalization

Avoid commits such as:

update stuff

changes

final

## Agent behavior

Before modifying code:

1. Read relevant steering files.
2. Read the relevant specification.
3. Inspect existing implementation.
4. Identify reusable code.
5. Plan the smallest required change.

After modifying code:

1. Run relevant tests.
2. Verify imports.
3. Verify the application if practical.
4. Report modified files.
5. Report tests executed.

Do not modify unrelated code.

Do not create unnecessary files.
