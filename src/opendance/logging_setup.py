"""Structured logging configuration for OpenDance AI.

Provides ISO 8601 timestamped, leveled log output to stderr.
Log level is controlled via the OPENDANCE_LOG_LEVEL environment variable.
"""

import logging
import os
import sys

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
ENV_VAR = "OPENDANCE_LOG_LEVEL"
VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def setup_logging() -> None:
    """Configure root logger with ISO 8601 timestamps, stderr output, and env-driven level.

    Reads the OPENDANCE_LOG_LEVEL environment variable (case-insensitive).
    Falls back to INFO if unset or invalid. Emits a warning on invalid value.
    """
    # Determine log level from environment
    env_value = os.environ.get(ENV_VAR, "").strip().upper()
    emit_invalid_warning = False

    if not env_value:
        level = logging.INFO
    elif env_value in VALID_LEVELS:
        level = getattr(logging, env_value)
    else:
        level = logging.INFO
        emit_invalid_warning = True

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates on repeated calls
    root_logger.handlers.clear()

    # Create stderr handler with ISO 8601 format
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Emit warning for invalid level after logger is configured
    if emit_invalid_warning:
        root_logger.warning(
            "Invalid %s value '%s' ignored. Defaulting to INFO.",
            ENV_VAR,
            os.environ.get(ENV_VAR, ""),
        )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger instance. Subpackages call this with __name__."""
    return logging.getLogger(name)
