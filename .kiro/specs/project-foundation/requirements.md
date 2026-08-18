# Requirements Document

## Introduction

This specification defines the project foundation (Phase 0) for OpenDance AI — the initial project structure, dependency management, configuration system, testing infrastructure, CI/CD pipeline, licensing, and application entry point. The foundation establishes the architectural skeleton upon which all subsequent features are built. Phase 0 does NOT implement any domain logic such as camera detection, MediaPipe inference, pose analysis, motion analysis, temporal alignment, scoring, machine learning, Practice mode, or Arcade mode. It provides only the scaffolding, packaging, and development tooling required to begin feature development.

The primary target platform for the MVP and future executable distribution is Windows 10/11 x64. The architecture should remain portable where practical, but cross-platform release validation is not required during Phase 0.

## Glossary

- **Project_Structure**: The directory layout of source code, tests, assets, scripts, and configuration files following the defined architecture.
- **Dependency_Manager**: The Python packaging tool (pip with pyproject.toml) responsible for declaring, resolving, and installing project dependencies.
- **Configuration_System**: The module responsible for loading, validating, and providing application settings including scoring thresholds, weights, and camera parameters. Phase 0 implements the configuration infrastructure only; no scoring engine or movement-scoring logic is implemented.
- **Test_Runner**: The pytest-based tooling that discovers and executes unit and integration tests.
- **CI_Pipeline**: The GitHub Actions workflow that runs linting, type checking, and tests on each push or pull request.
- **Application_Entry_Point**: The module that initializes the PySide6 application, creates the main window, and starts the Qt event loop.
- **Logging_System**: The structured logging module that provides consistent log formatting and level control across all subpackages.
- **Package**: The installable Python package defined by pyproject.toml that allows the application to be installed in development or distribution mode.

## Requirements

### Requirement 1: Project Directory Structure

**User Story:** As a developer, I want a well-organized project directory structure, so that I can locate and maintain code across architectural layers without ambiguity.

#### Acceptance Criteria

1. THE Project_Structure SHALL contain a `src/opendance/` root package with an `__init__.py` file and subpackages: `app`, `ui`, `camera`, `video`, `pose`, `motion`, `alignment`, `scoring`, `analytics`, `storage`, `config`.
2. THE Project_Structure SHALL contain a `tests/` directory with subdirectories: `unit`, `integration`, `fixtures`.
3. THE Project_Structure SHALL contain an `assets/` directory with subdirectories: `models`, `demo`.
4. THE Project_Structure SHALL contain a `scripts/` directory for development and utility scripts.
5. THE Project_Structure SHALL contain a `.github/workflows/` directory for CI/CD pipeline definitions.
6. THE Project_Structure SHALL include an `__init__.py` file in `src/opendance/` and in each of its subpackage directories (`app`, `ui`, `camera`, `video`, `pose`, `motion`, `alignment`, `scoring`, `analytics`, `storage`, `config`) to make them valid Python packages.
7. THE `src/opendance/__init__.py` file SHALL expose a module-level `__version__` variable set to `"0.1.0"` matching the version declared in pyproject.toml.
8. THE Project_Structure SHALL NOT require `__init__.py` files in `tests/` subdirectories, as pytest discovers tests without package markers in the src layout.

### Requirement 2: Python Package Configuration

**User Story:** As a developer, I want a standard Python package configuration, so that I can install the project in development mode and manage dependencies consistently.

#### Acceptance Criteria

1. THE Package SHALL be defined using a `pyproject.toml` file at the repository root that declares a `[build-system]` section specifying `setuptools` as the build backend and `setuptools>=68.0` as the build requirement.
2. THE Package SHALL declare Python 3.10 or higher as the minimum required version using the `requires-python` field.
3. THE Package SHALL declare the project name as `opendance` in the `[project]` section of pyproject.toml.
4. THE Package SHALL declare an initial version of `0.1.0` in pyproject.toml.
5. THE Package SHALL declare the following core runtime dependencies with minimum version constraints (using `>=` specifiers): PySide6, opencv-python, mediapipe, numpy, scipy, and `tomli; python_version < "3.11"` for TOML parsing compatibility on Python 3.10.
6. THE Package SHALL declare development dependencies in a `[project.optional-dependencies]` group named `dev`, including: pytest, pytest-cov, ruff, mypy.
7. THE Package SHALL use the `src` layout so that `src/opendance` is the importable package.
8. THE Package SHALL define a console entry point named `opendance` that maps to the `src/opendance/app/main.py:main` function.
9. THE Package SHALL include setuptools package-data configuration so that `defaults.toml` in the `opendance.config` subpackage is included in built distributions.
10. WHEN a developer runs `pip install -e .` in the repository root, THE Package SHALL install the project in editable mode with all runtime dependencies resolved.
11. WHEN a developer runs `pip install -e ".[dev]"` in the repository root, THE Package SHALL install the project in editable mode with both runtime and development dependencies resolved.

### Requirement 3: Configuration System

**User Story:** As a developer, I want a centralized configuration system, so that scoring thresholds, weights, camera settings, and application parameters are not hardcoded throughout the codebase.

#### Acceptance Criteria

1. THE Configuration_System SHALL load default configuration values from a bundled TOML defaults file.
2. THE Configuration_System SHALL allow user-specific overrides via a local TOML configuration file located in a platform-appropriate user configuration directory.
3. THE Configuration_System SHALL expose configuration values as typed Python objects using dataclasses.
4. THE Configuration_System SHALL include default scoring thresholds: PERFECT (90.0–100.0), GREAT (75.0–89.99), OK (50.0–74.99), MEH (30.0–49.99), MISS (below 30.0).
5. THE Configuration_System SHALL include default scoring weights: pose_similarity=0.40, angle_similarity=0.25, motion_similarity=0.20, timing_similarity=0.15.
6. WHEN the local configuration file contains a partial set of values, THE Configuration_System SHALL merge user-provided values with the defaults, applying user values only to the specified keys and retaining defaults for all unspecified keys.
7. IF the local configuration file contains values with wrong data types or values outside permitted ranges, THEN THE Configuration_System SHALL log a warning identifying the invalid entry and fall back to the default value for that specific entry.
8. THE Configuration_System SHALL enforce the following validation ranges: scoring threshold values must be between 0.0 and 100.0 inclusive; scoring weight values must be between 0.0 and 1.0 inclusive.
9. THE Configuration_System SHALL NOT validate that scoring weights sum to 1.0 in Phase 0. Validation of weight-sum constraints is deferred to the future scoring engine specification. Phase 0 stores individually valid weights as provided.
10. IF the local configuration file does not exist, THEN THE Configuration_System SHALL operate using only default values without raising an error.
11. IF the local configuration file contains malformed TOML that cannot be parsed, THEN THE Configuration_System SHALL log a warning and fall back to all default values.
12. THE Configuration_System SHALL be independently testable without requiring any UI, camera, or video components.
13. THE Configuration_System SHALL NOT implement any scoring engine or movement-scoring logic in Phase 0. Scoring thresholds and weights are stored as project configuration values only; their consumption by a scoring engine is deferred to later specifications.

### Requirement 4: Logging System

**User Story:** As a developer, I want a consistent logging system, so that all subpackages produce structured, leveled log output useful for debugging and monitoring.

#### Acceptance Criteria

1. THE Logging_System SHALL configure Python's standard `logging` module with a format that includes ISO 8601 timestamp, log level name, logger name, and message in each log record.
2. THE Logging_System SHALL support log level configuration via an environment variable (e.g., `OPENDANCE_LOG_LEVEL`) accepting values DEBUG, INFO, WARNING, ERROR, or CRITICAL (case-insensitive).
3. IF the `OPENDANCE_LOG_LEVEL` environment variable is not set, THEN THE Logging_System SHALL default to INFO level.
4. THE Logging_System SHALL output to stderr by default.
5. THE Logging_System SHALL provide a function that subpackages call to obtain a logger instance named with the calling module's `__name__` attribute.
6. THE Logging_System SHALL not log raw camera frames, raw video data, or personal user information.
7. IF the `OPENDANCE_LOG_LEVEL` environment variable contains an invalid value, THEN THE Logging_System SHALL fall back to INFO level and emit a warning log message indicating the invalid value was ignored.

### Requirement 5: Application Entry Point

**User Story:** As a user, I want to launch the OpenDance AI application from the command line, so that I can start using the desktop application.

#### Acceptance Criteria

1. WHEN the `opendance` command is executed, THE Application_Entry_Point SHALL create a PySide6 QApplication instance.
2. WHEN the QApplication is created, THE Application_Entry_Point SHALL create and display a main window with the title "OpenDance AI" and a minimum size of 800×600 pixels.
3. WHEN the main window is displayed, THE Application_Entry_Point SHALL start the Qt event loop.
4. IF an unhandled exception occurs before the Qt event loop begins processing events, THEN THE Application_Entry_Point SHALL log the error and exit with a non-zero exit code.
5. THE Application_Entry_Point SHALL initialize the Logging_System before initializing the Configuration_System and before creating any UI components.
6. THE Application_Entry_Point SHALL initialize the Configuration_System after the Logging_System and before creating any UI components.
7. IF the Configuration_System fails to initialize, THEN THE Application_Entry_Point SHALL log an error message indicating the configuration failure, fall back to default configuration values, and continue startup.
8. IF the Logging_System fails to initialize, THEN THE Application_Entry_Point SHALL write the error to stderr and continue startup with standard logging defaults.
9. WHEN the Application_Entry_Point is executed in a test environment without a physical camera, THE Application_Entry_Point SHALL initialize the PySide6 QApplication and main window successfully without attempting camera access or failing due to absent camera hardware.

### Requirement 6: Test Infrastructure

**User Story:** As a developer, I want a working test infrastructure, so that I can write and run tests for every algorithm and module from the beginning of the project.

#### Acceptance Criteria

1. THE Test_Runner SHALL discover and execute all tests in the `tests/` directory using pytest with configuration defined in `pyproject.toml`.
2. THE Test_Runner SHALL be invocable via a single command documented in the README.
3. THE Test_Runner SHALL support code coverage reporting via pytest-cov measuring the `src/opendance` package.
4. THE Test_Runner SHALL separate unit tests from integration tests by directory structure (`tests/unit/` and `tests/integration/`) and SHALL support running each category independently via pytest markers or path arguments.
5. WHEN all tests pass, THE Test_Runner SHALL exit with code 0.
6. WHEN any test fails, THE Test_Runner SHALL exit with a non-zero code and report the names of failing tests and their failure reasons.
7. THE Test_Runner SHALL include at least one passing unit test that verifies the Configuration_System loads default scoring thresholds (PERFECT, GREAT, OK, MEH, MISS) and default scoring weights (pose_similarity, angle_similarity, motion_similarity, timing_similarity) matching the values defined in the bundled defaults file.
8. THE Test_Runner SHALL include at least one passing unit test that verifies the Logging_System initializes without raising an exception and returns a usable logger instance.
9. WHEN a developer runs tests with coverage enabled, THE Test_Runner SHALL generate a coverage report indicating the percentage of lines covered in `src/opendance`.

### Requirement 7: CI/CD Pipeline

**User Story:** As a developer, I want an automated CI pipeline, so that code quality and test coverage are verified on every push and pull request.

#### Acceptance Criteria

1. THE CI_Pipeline SHALL be defined as a GitHub Actions workflow file located in the `.github/workflows/` directory.
2. WHEN a push or pull request targets the main branch, THE CI_Pipeline SHALL run linting by executing ruff against the entire repository.
3. WHEN a push or pull request targets the main branch, THE CI_Pipeline SHALL run type checking by executing mypy against the `src/` directory.
4. WHEN a push or pull request targets the main branch, THE CI_Pipeline SHALL run all tests by executing pytest against the `tests/` directory with coverage collection enabled.
5. THE CI_Pipeline SHALL test against Python 3.10 and Python 3.11 only, without a larger version matrix.
6. IF any CI step fails, THEN THE CI_Pipeline SHALL report a failing status on the commit or pull request.
7. THE CI_Pipeline SHALL install the project in editable mode with development dependencies before running checks.
8. THE CI_Pipeline SHALL execute workflow steps in the following order: install dependencies, run linting, run type checking, run tests.
9. THE CI_Pipeline SHALL set the environment variable `QT_QPA_PLATFORM=offscreen` before running tests to allow PySide6 QApplication creation without a display server on headless CI.
10. THE CI_Pipeline SHALL cover Windows-specific configuration-path behavior through unit tests using mocked environment variables rather than requiring a Windows CI runner.

### Requirement 8: README Documentation

**User Story:** As a developer or contributor, I want clear project documentation, so that I can understand the project purpose, set up the development environment, and run tests.

#### Acceptance Criteria

1. THE Project_Structure SHALL include a `README.md` at the repository root.
2. THE README.md SHALL describe OpenDance AI as an open-source desktop application for dance practice, movement analysis, and rhythm-game-style scoring that compares user movement captured via camera against a reference dance video.
3. THE README.md SHALL document prerequisites including the minimum Python version (3.10 or higher), the primary target platform (Windows 10/11 x64), and note that the architecture is portable where practical.
4. THE README.md SHALL document installation steps including virtual environment creation, editable install command (`pip install -e .`), and verification that the install succeeded.
5. THE README.md SHALL document the command to run all tests using pytest.
6. THE README.md SHALL document the commands to run linting (`ruff check .`) and type checking (`mypy src/`).
7. THE README.md SHALL document the project directory structure overview covering `src/opendance/`, `tests/`, `assets/`, and `scripts/` directories.
8. THE README.md SHALL document how to launch the application using the `opendance` console command after installation.
9. THE README.md SHALL include a license reference indicating the project is released under the MIT License.

### Requirement 9: Code Quality Tooling Configuration

**User Story:** As a developer, I want pre-configured linting and type checking, so that code style and type safety are enforced consistently across the codebase.

#### Acceptance Criteria

1. THE Package SHALL configure ruff for linting in pyproject.toml with a line length of 100 characters and enable at minimum the pyflakes (F), pycodestyle (E, W), and isort (I) rule sets.
2. THE Package SHALL configure ruff to enforce import sorting with `opendance` declared as a known first-party package.
3. THE Package SHALL configure mypy in pyproject.toml with strict mode disabled and the following checks enabled globally: warn_return_any, warn_unused_configs, disallow_untyped_defs, and ignore_missing_imports set to true for third-party libraries lacking type stubs. The checked package is limited to `src/opendance` via the `packages` and `mypy_path` directives.
4. THE Package SHALL configure mypy to check the `src/opendance` package by specifying it in the mypy configuration section.
5. WHEN a developer runs `ruff check .` on the initial project skeleton, THE linting configuration SHALL produce zero warnings with exit code 0.
6. WHEN a developer runs `mypy src/` on the initial project skeleton, THE type checking configuration SHALL produce zero errors with exit code 0.
7. THE Package SHALL configure ruff to exclude virtual environment directories, build artifacts, and the `.venv` directory from linting scope.

### Requirement 10: Git Repository Configuration

**User Story:** As a developer, I want proper Git configuration files, so that generated files, caches, and OS artifacts are excluded from version control.

#### Acceptance Criteria

1. THE Project_Structure SHALL include a `.gitignore` file at the repository root.
2. THE .gitignore SHALL exclude Python bytecode files (`__pycache__/`, `*.pyc`, `*.pyo`).
3. THE .gitignore SHALL exclude virtual environment directories (`venv/`, `.venv/`, `env/`).
4. THE .gitignore SHALL exclude build artifacts (`dist/`, `build/`, `*.egg-info`).
5. THE .gitignore SHALL exclude IDE configuration directories (`.idea/`, `.vscode/`).
6. THE .gitignore SHALL exclude OS-specific files (`.DS_Store`, `Thumbs.db`).
7. THE .gitignore SHALL exclude coverage reports (`.coverage`, `htmlcov/`).
8. THE .gitignore SHALL exclude environment variable files (`.env`, `.env.*`) to prevent secrets from being committed.
9. THE .gitignore SHALL exclude tool cache directories (`.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`).
10. THE .gitignore SHALL exclude local log files (`*.log`).

### Requirement 11: Open-Source License

**User Story:** As a contributor or user, I want a clear open-source license, so that the legal terms for using, modifying, and distributing the software are unambiguous.

#### Acceptance Criteria

1. THE Project_Structure SHALL include a `LICENSE` file at the repository root.
2. THE LICENSE file SHALL contain the full text of the MIT License.
3. THE LICENSE file SHALL specify the copyright year and copyright holder appropriate for the project.

### Requirement 12: Phase 0 Scope Boundaries

**User Story:** As a developer, I want explicit boundaries on what Phase 0 delivers, so that implementation remains focused on foundational infrastructure without scope creep into domain features.

#### Acceptance Criteria

1. THE Project_Structure SHALL NOT implement camera detection or camera frame acquisition logic in Phase 0.
2. THE Project_Structure SHALL NOT implement MediaPipe pose inference or any pose-estimation logic in Phase 0.
3. THE Project_Structure SHALL NOT implement pose analysis, motion analysis, or temporal alignment algorithms in Phase 0.
4. THE Project_Structure SHALL NOT implement a scoring engine or any movement-scoring logic in Phase 0.
5. THE Project_Structure SHALL NOT implement machine learning model loading or inference in Phase 0.
6. THE Project_Structure SHALL NOT implement Practice mode or Arcade mode in Phase 0.
7. THE Project_Structure SHALL NOT introduce a database, web server, cloud service, authentication system, remote AI service, or network backend in Phase 0.
8. THE Project_Structure SHALL NOT introduce dependencies or infrastructure beyond what is required by the other Phase 0 requirements.
