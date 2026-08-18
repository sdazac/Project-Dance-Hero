# OpenDance AI

An open-source desktop application for dance practice, movement analysis, and rhythm-game-style scoring. OpenDance AI compares user movement captured via camera against a reference dance video.

## Prerequisites

- **Python 3.10 or higher**
- **Primary target platform:** Windows 10/11 x64
- The architecture is portable where practical

## Installation

1. Create a virtual environment:

```bash
python -m venv .venv
```

2. Activate the virtual environment:

```bash
# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

3. Install in editable mode:

```bash
pip install -e .
```

4. For development (includes test and lint tools):

```bash
pip install -e ".[dev]"
```

5. Verify the install:

```bash
python -c "import opendance; print(opendance.__version__)"
```

## Usage

Launch the application:

```bash
opendance
```

## Running Tests

Run all tests:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=opendance --cov-report=term-missing
```

Run unit tests only:

```bash
pytest tests/unit/
```

Run integration tests only:

```bash
pytest tests/integration/
```

## Code Quality

Run linting:

```bash
ruff check .
```

Run type checking:

```bash
mypy src/
```

## Project Structure

```
src/opendance/       # Main application package
  app/               # Application entry point
  ui/                # User interface (PySide6 widgets)
  camera/            # Camera capture and management
  video/             # Reference video loading and playback
  pose/              # Pose detection (MediaPipe)
  motion/            # Motion feature extraction
  alignment/         # Temporal alignment algorithms
  scoring/           # Scoring and grading engine
  analytics/         # Performance analytics
  storage/           # Cache and persistence
  config/            # Configuration system

tests/               # Test suite
  unit/              # Unit tests
  integration/       # Integration tests
  fixtures/          # Test fixtures and data

assets/              # Static assets
  models/            # ML models
  demo/              # Demo media

scripts/             # Development and utility scripts
```

## License

This project is released under the [MIT License](LICENSE).
