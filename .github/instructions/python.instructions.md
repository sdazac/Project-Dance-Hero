# Python Code Instructions — OpenDance AI

applyTo: "src/**/*.py"

## Style and Conventions

Follow the rules in `.kiro/steering/coding-standards.md`. Key points:

- Python 3.10+ with type hints on all public functions and methods.
- Use `snake_case` for variables/functions, `PascalCase` for classes, `UPPER_CASE` for constants.
- Prefer small functions with one clear responsibility.
- Use `dataclasses` (frozen when appropriate) for domain objects.
- Line length: 100 characters (configured in pyproject.toml ruff section).
- Import sorting: `opendance` is a known first-party package (isort configured).

## Architecture Rules

Read `.kiro/steering/architecture.md` for full layer definitions.

- **Separation of concerns**: UI widgets must not contain pose analysis, scoring, or camera I/O logic.
- **No blocking the UI thread**: Camera frame acquisition and MediaPipe inference run on background threads (QThread).
- **No global mutable state** without explicit justification.
- **Reuse initialized resources**: Do not reinitialize MediaPipe models or VideoCapture per frame.

## Configuration

Never hardcode configurable values. Use the configuration system:

```python
from opendance.config import load_config
config = load_config()
# Access: config.camera_config.device_index, config.pose_config.model_path, etc.
```

New configurable values: add to `defaults.toml`, create a frozen dataclass in `models.py`, extend `_build_config()` in `loader.py` with validation.

## Logging

Use the project's logging system:

```python
from opendance.logging_setup import get_logger
logger = get_logger(__name__)
```

- Never log raw camera frames or personal user data.
- Log initialization events, errors, and state transitions.
- Use appropriate levels: DEBUG for diagnostics, INFO for state changes, WARNING for recoverable issues, ERROR for failures.

## Error Handling

- Handle expected failures explicitly (camera unavailable, model missing, malformed config).
- User-facing errors must be understandable (no raw tracebacks in the UI).
- Technical details go to the log.
- Never silently swallow errors — at minimum log them.

## Privacy

Read `.kiro/steering/privacy.md`. All processing is local:

- No network transmission of frame data.
- No recording/persisting frames unless user explicitly enables a future feature.
- No logging of frame pixel data at any level.
