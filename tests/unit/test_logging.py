"""Unit tests for the OpenDance AI logging system.

Tests cover:
- setup_logging() completes without exception
- Valid OPENDANCE_LOG_LEVEL values set correct level (case-insensitive)
- Invalid OPENDANCE_LOG_LEVEL results in INFO + warning emitted
- Missing OPENDANCE_LOG_LEVEL defaults to INFO
- get_logger(__name__) returns Logger with expected name
- Log format contains ISO 8601 timestamp, level, logger name, message
"""

import logging
from unittest.mock import patch

import pytest

from opendance.logging_setup import ENV_VAR, get_logger, setup_logging


class TestLoggingInitialization:
    """Test setup_logging() completes without exception."""

    def test_setup_logging_no_exception(self) -> None:
        with patch.dict("os.environ", {ENV_VAR: "INFO"}):
            setup_logging()


class TestLogLevelHandling:
    """Test valid log levels set correctly (case-insensitive)."""

    def test_debug_level(self) -> None:
        with patch.dict("os.environ", {ENV_VAR: "DEBUG"}):
            setup_logging()
        assert logging.getLogger().level == logging.DEBUG

    def test_info_level(self) -> None:
        with patch.dict("os.environ", {ENV_VAR: "INFO"}):
            setup_logging()
        assert logging.getLogger().level == logging.INFO

    def test_warning_level(self) -> None:
        with patch.dict("os.environ", {ENV_VAR: "WARNING"}):
            setup_logging()
        assert logging.getLogger().level == logging.WARNING

    def test_error_level(self) -> None:
        with patch.dict("os.environ", {ENV_VAR: "ERROR"}):
            setup_logging()
        assert logging.getLogger().level == logging.ERROR

    def test_critical_level(self) -> None:
        with patch.dict("os.environ", {ENV_VAR: "CRITICAL"}):
            setup_logging()
        assert logging.getLogger().level == logging.CRITICAL

    def test_case_insensitive_lowercase(self) -> None:
        with patch.dict("os.environ", {ENV_VAR: "debug"}):
            setup_logging()
        assert logging.getLogger().level == logging.DEBUG

    def test_case_insensitive_mixed(self) -> None:
        with patch.dict("os.environ", {ENV_VAR: "Warning"}):
            setup_logging()
        assert logging.getLogger().level == logging.WARNING


class TestInvalidLogLevel:
    """Test invalid OPENDANCE_LOG_LEVEL results in INFO + warning."""

    def test_invalid_level_defaults_to_info(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with patch.dict("os.environ", {ENV_VAR: "BOGUS"}):
            setup_logging()
        assert logging.getLogger().level == logging.INFO

    def test_invalid_level_emits_warning(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch.dict("os.environ", {ENV_VAR: "INVALID_VALUE"}):
            setup_logging()
        captured = capsys.readouterr()
        assert "INVALID_VALUE" in captured.err


class TestMissingLogLevel:
    """Test missing env var defaults to INFO."""

    def test_unset_env_defaults_to_info(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            setup_logging()
        assert logging.getLogger().level == logging.INFO


class TestLoggerCreation:
    """Test get_logger returns Logger with expected name."""

    def test_get_logger_returns_logger(self) -> None:
        logger = get_logger("opendance.test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "opendance.test.module"

    def test_get_logger_with_dunder_name(self) -> None:
        logger = get_logger(__name__)
        assert isinstance(logger, logging.Logger)
        assert logger.name == __name__


class TestLogFormat:
    """Test formatted output contains required components."""

    def test_format_contains_all_components(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch.dict("os.environ", {ENV_VAR: "DEBUG"}):
            setup_logging()

        logger = get_logger("opendance.test.format")
        logger.info("test format message")

        # Log goes to stderr
        captured = capsys.readouterr()
        stderr_output = captured.err

        # Verify ISO 8601 timestamp pattern (YYYY-MM-DDThh:mm:ss)
        assert "T" in stderr_output  # ISO 8601 separator
        # Verify level name
        assert "[INFO]" in stderr_output
        # Verify logger name
        assert "opendance.test.format" in stderr_output
        # Verify message
        assert "test format message" in stderr_output
