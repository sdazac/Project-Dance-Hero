# Test Instructions — OpenDance AI

applyTo: "tests/**/*.py"

## Testing Framework

- **pytest** for test execution.
- **hypothesis** for property-based testing where applicable.
- **pytest-cov** for coverage measurement.
- **QT_QPA_PLATFORM=offscreen** required for any test that creates Qt widgets.

## Key Rules

Read `.kiro/steering/testing.md` for full strategy.

- **No physical hardware**: All tests must work without a camera, GPU, or network.
- **Mock camera**: Use `unittest.mock.MagicMock` for `cv2.VideoCapture`.
- **Mock MediaPipe**: Bypass real model loading — inject mock landmarker results.
- **Synthetic frames**: Use `np.zeros((h, w, 3), dtype=np.uint8)` or similar.
- **Deterministic inputs**: Prefer explicit synthetic data over random unless using hypothesis.

## Test Structure

```
tests/
├── unit/           # Fast, isolated, no I/O
├── integration/    # Cross-module (camera + pose together, still mocked)
└── fixtures/       # Shared test data
```

- No `__init__.py` in test directories (pytest src-layout discovery).
- Test files: `test_<module_name>.py`
- Test classes: `class Test<Feature>:`
- Test methods: `def test_<behavior>(self):`

## What to Test

Per `.kiro/steering/testing.md`:

- Configuration loading, merging, validation
- Pose result structure and immutability
- FPS calculation with various timing patterns
- Skeleton renderer visibility filtering
- Camera state machine transitions
- Frame worker consecutive failure threshold
- UI control enable/disable per state
- Resource cleanup (release called, threads terminated)
- Error handling (no unhandled exceptions escape)

## Boundary Tests (Required)

Explicitly test boundaries for:
- Scoring thresholds: 0.0, 30.0, 49.99, 50.0, 74.99, 75.0, 89.99, 90.0, 100.0
- Visibility threshold: 0.0, 0.5, 1.0, exact-threshold values
- Configuration ranges: min/max valid, just outside range

## Property-Based Tests

Use hypothesis for:
- FPS calculation (monotonic timestamp sequences)
- Skeleton rendering (random landmarks with random thresholds)
- Configuration validation (random invalid types/values)
- PoseResult construction (random landmark data)

```python
from hypothesis import given, settings
from hypothesis.strategies import floats, lists

@given(timestamps=lists(floats(min_value=0.0, max_value=1000.0, ...), min_size=2))
@settings(max_examples=100)
def test_fps_formula(self, timestamps):
    ...
```

## Qt Widget Tests

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app
```

## Verification Commands

```bash
# All tests
pytest tests/

# With coverage
pytest tests/ --cov=opendance --cov-report=term-missing

# Single test file
pytest tests/unit/test_<module>.py -v --tb=short
```
