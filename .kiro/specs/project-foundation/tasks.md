# Implementation Plan: Project Foundation (Phase 0)

## Overview

This plan implements the foundational project infrastructure for OpenDance AI. It establishes the Python package structure, configuration system, logging system, minimal PySide6 entry point, test infrastructure, CI/CD pipeline, and code quality tooling. All tasks produce code artifacts only — no domain logic is implemented.

## Tasks

- [ ] 1. Set up project package configuration and directory structure
  - [x] 1.1 Create pyproject.toml with build system, dependencies, and tooling configuration
    - Define `[build-system]` with setuptools>=68.0
    - Define `[project]` section: name=opendance, version=0.1.0, requires-python>=3.10
    - Declare runtime dependencies: PySide6>=6.5, opencv-python>=4.8, mediapipe>=0.10, numpy>=1.24, scipy>=1.10, `tomli>=2.0; python_version < "3.11"`
    - Declare `[project.optional-dependencies]` dev group: pytest>=7.0, pytest-cov>=4.0, ruff>=0.1, mypy>=1.0
    - Define console entry point: `opendance = "opendance.app.main:main"`
    - Configure `[tool.setuptools.packages.find]` with `where = ["src"]`
    - Configure `[tool.setuptools.package-data]` for `opendance.config = ["defaults.toml"]`
    - Configure `[tool.pytest.ini_options]` with testpaths and markers
    - Configure `[tool.ruff]` with line-length=100, exclude dirs, lint select F/E/W/I, isort known-first-party
    - Configure `[tool.mypy]` with packages, mypy_path, warn_return_any, warn_unused_configs, disallow_untyped_defs, ignore_missing_imports
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 9.1, 9.2, 9.3, 9.4, 9.7_

  - [x] 1.2 Create src/opendance package structure with __init__.py files
    - Create `src/opendance/__init__.py` exposing `__version__ = "0.1.0"`
    - Create `__init__.py` in each subpackage: app, ui, camera, video, pose, motion, alignment, scoring, analytics, storage, config
    - _Requirements: 1.1, 1.6, 1.7_

  - [x] 1.3 Create remaining directory structure (tests, assets, scripts)
    - Create `tests/unit/`, `tests/integration/`, `tests/fixtures/` directories
    - Create `assets/models/`, `assets/demo/` directories
    - Create `scripts/` directory
    - Create `.github/workflows/` directory
    - Note: no `__init__.py` in tests directories per requirement 1.8
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.8_

- [ ] 2. Implement configuration system
  - [x] 2.1 Create configuration dataclass models (src/opendance/config/models.py)
    - Define `ScoringThresholds` frozen dataclass with fields: perfect_min=90.0, great_min=75.0, ok_min=50.0, meh_min=30.0
    - Define `ScoringWeights` frozen dataclass with fields: pose_similarity=0.40, angle_similarity=0.25, motion_similarity=0.20, timing_similarity=0.15
    - Define `AppConfig` frozen dataclass composing ScoringThresholds and ScoringWeights with default_factory
    - All dataclasses must use `frozen=True`
    - _Requirements: 3.3, 3.4, 3.5, 3.12_

  - [x] 2.2 Create bundled defaults.toml (src/opendance/config/defaults.toml)
    - Define `[scoring.thresholds]` section with perfect_min, great_min, ok_min, meh_min values
    - Define `[scoring.weights]` section with pose_similarity, angle_similarity, motion_similarity, timing_similarity values
    - _Requirements: 3.1, 3.4, 3.5_

  - [x] 2.3 Implement configuration loader (src/opendance/config/loader.py)
    - Implement TOML import compatibility: use `tomllib` on Python 3.11+, `tomli` on 3.10
    - Implement `get_user_config_path()`: use `%APPDATA%\opendance\config.toml` on Windows, `~/.config/opendance/config.toml` otherwise
    - Implement `merge_toml(defaults, overrides)`: deep-merge override dict into defaults (override wins per-key)
    - Implement `validate_value(key, value, expected_type, valid_range)`: validate type and range, return default on failure with warning logged
    - Implement `load_config(defaults_path, user_path)`: load defaults via importlib.resources, optionally load user config, merge, validate, construct AppConfig
    - Handle missing user config silently (use defaults only)
    - Handle malformed TOML (log warning, use all defaults)
    - Handle invalid values per-key (log warning per key, use default for that key)
    - Enforce ranges: thresholds 0.0–100.0, weights 0.0–1.0
    - Do NOT validate weight sum
    - Export `load_config` from `src/opendance/config/__init__.py`
    - _Requirements: 3.1, 3.2, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13_

- [ ] 3. Implement logging system
  - [x] 3.1 Implement logging setup module (src/opendance/logging_setup.py)
    - Define LOG_FORMAT with ISO 8601 timestamp, level, logger name, and message
    - Define LOG_DATE_FORMAT as `%Y-%m-%dT%H:%M:%S%z`
    - Define ENV_VAR = "OPENDANCE_LOG_LEVEL" and VALID_LEVELS set
    - Implement `setup_logging()`: configure root logger with StreamHandler(stderr), read env var (case-insensitive), default to INFO if unset or invalid, emit warning on invalid value
    - Implement `get_logger(name)`: return `logging.getLogger(name)`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [ ] 4. Implement application entry point
  - [x] 4.1 Implement main function (src/opendance/app/main.py)
    - Import and call `setup_logging()` first; if it raises, write error to stderr and continue
    - Import and call `load_config()` second; if it raises, log error and use default AppConfig()
    - Create `QApplication(sys.argv)`
    - Create `QMainWindow`, set window title "OpenDance AI", set minimum size 800×600
    - Show main window
    - Return `app.exec()` to start Qt event loop
    - Handle unhandled exceptions before event loop: log error, return non-zero exit code
    - Include `if __name__ == "__main__": sys.exit(main())`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_

- [x] 5. Checkpoint - Verify core implementation
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement test suite
  - [x] 6.1 Create configuration unit tests (tests/unit/test_config.py)
    - Test default loading produces correct threshold and weight values
    - Test partial user override merges correctly (overridden keys take user values, others retain defaults)
    - Test invalid type values (string where float expected) fall back to default with warning
    - Test out-of-range values (threshold >100 or <0, weight >1 or <0) fall back to default
    - Test boundary values (0.0, 100.0, 1.0) are accepted
    - Test weight-sum is NOT validated (all weights=0.90 accepted)
    - Test malformed TOML falls back to all defaults with warning
    - Test missing user config loads defaults without error
    - Test `get_user_config_path()` returns correct path on Windows (mock os.environ with APPDATA, mock sys.platform)
    - Test `get_user_config_path()` returns correct path on non-Windows (mock sys.platform)
    - _Requirements: 3.1, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 6.7_

  - [x] 6.2 Create logging unit tests (tests/unit/test_logging.py)
    - Test `setup_logging()` completes without exception
    - Test valid OPENDANCE_LOG_LEVEL values (DEBUG, INFO, WARNING, ERROR, CRITICAL, case-insensitive) set correct level
    - Test invalid OPENDANCE_LOG_LEVEL results in INFO and warning emitted
    - Test missing OPENDANCE_LOG_LEVEL defaults to INFO
    - Test `get_logger(__name__)` returns Logger instance with expected name
    - Test formatted output contains ISO 8601 timestamp, level, logger name, message
    - _Requirements: 4.1, 4.2, 4.3, 4.7, 6.8_

  - [x] 6.3 Create application entry point unit tests (tests/unit/test_main.py)
    - Test `main()` calls setup_logging before load_config (initialization order)
    - Test configuration failure resilience: load_config raises → continues with default AppConfig
    - Test logging failure resilience: setup_logging raises → writes to stderr, continues
    - Test window title is "OpenDance AI" and minimum size is 800×600
    - Set QT_QPA_PLATFORM=offscreen for headless testing
    - _Requirements: 5.1, 5.2, 5.5, 5.6, 5.7, 5.8, 5.9, 6.4_

- [x] 7. Checkpoint - Ensure all unit tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Set up CI/CD pipeline and repository files
  - [x] 8.1 Create GitHub Actions CI workflow (.github/workflows/ci.yml)
    - Trigger on push and pull_request to main branch
    - Use matrix strategy for Python 3.10 and 3.11
    - Set env `QT_QPA_PLATFORM: offscreen` at job level
    - Steps: checkout, setup-python, `pip install -e ".[dev]"`, `ruff check .`, `mypy src/`, `pytest --cov=opendance --cov-report=term-missing`
    - Run on ubuntu-latest
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10_

  - [x] 8.2 Create .gitignore file
    - Exclude Python bytecode: `__pycache__/`, `*.pyc`, `*.pyo`
    - Exclude virtual environments: `venv/`, `.venv/`, `env/`
    - Exclude build artifacts: `dist/`, `build/`, `*.egg-info`
    - Exclude IDE directories: `.idea/`, `.vscode/`
    - Exclude OS files: `.DS_Store`, `Thumbs.db`
    - Exclude coverage: `.coverage`, `htmlcov/`
    - Exclude env files: `.env`, `.env.*`
    - Exclude tool caches: `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
    - Exclude log files: `*.log`
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10_

  - [x] 8.3 Create LICENSE file (MIT License)
    - Include full MIT License text with appropriate copyright year and holder
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 8.4 Create README.md
    - Describe OpenDance AI as open-source desktop application for dance practice, movement analysis, and rhythm-game-style scoring
    - Document prerequisites: Python 3.10+, Windows 10/11 x64 primary target, portable where practical
    - Document installation: virtual environment creation, `pip install -e .`, verification
    - Document running tests: `pytest` command
    - Document linting: `ruff check .` and type checking: `mypy src/`
    - Document project directory structure overview (src/opendance/, tests/, assets/, scripts/)
    - Document launching application: `opendance` console command
    - Include MIT License reference
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9_

- [x] 9. Final checkpoint - Verify complete project
  - Ensure all tests pass, ask the user if questions arise.
  - Verify `ruff check .` produces zero warnings
  - Verify `mypy src/` produces zero errors
  - Verify `pip install -e ".[dev]"` succeeds
  - Verify all requirement coverage is complete

## Notes

- No property-based tests are included in Phase 0 — the design explicitly states correctness properties are deferred to later phases with domain algorithms
- Tests use mocked `os.environ` and `sys.platform` to verify Windows config paths on any CI runner
- QT_QPA_PLATFORM=offscreen must be set for application entry point tests (headless)
- Phase 0 does NOT implement any domain logic (camera, pose, motion, scoring, alignment, analytics)
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["2.1", "2.2", "3.1"] },
    { "id": 3, "tasks": ["2.3", "4.1"] },
    { "id": 4, "tasks": ["6.1", "6.2", "6.3"] },
    { "id": 5, "tasks": ["8.1", "8.2", "8.3", "8.4"] }
  ]
}
```
