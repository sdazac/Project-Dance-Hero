"""Configuration loading, merging, and validation for OpenDance AI."""

import importlib.resources
import logging
import os
import sys
from pathlib import Path
from typing import Any

# TOML parsing: use stdlib tomllib on Python 3.11+, fall back to tomli on 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from opendance.config.models import AppConfig, ScoringThresholds, ScoringWeights

logger = logging.getLogger(__name__)

# Validation ranges per field category
_THRESHOLD_RANGE = (0.0, 100.0)
_WEIGHT_RANGE = (0.0, 1.0)

_THRESHOLD_FIELDS = {"perfect_min", "great_min", "ok_min", "meh_min"}
_WEIGHT_FIELDS = {"pose_similarity", "angle_similarity", "motion_similarity", "timing_similarity"}


def get_user_config_path() -> Path:
    """Return platform-appropriate user config file path.

    Primary target (Windows): %APPDATA%\\opendance\\config.toml
    Fallback (non-Windows):   ~/.config/opendance/config.toml
    """
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "opendance" / "config.toml"
    return Path.home() / ".config" / "opendance" / "config.toml"


def merge_toml(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge override dict into defaults dict (override wins per-key).

    For nested dicts, merges recursively. For leaf values, override replaces default.
    """
    merged = dict(defaults)
    for key, value in overrides.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = merge_toml(merged[key], value)
        else:
            merged[key] = value
    return merged


def validate_value(
    key: str,
    value: Any,
    expected_type: type,
    valid_range: tuple[float, float] | None = None,
    default: Any = None,
) -> Any:
    """Validate a config value's type and range, returning default on failure.

    Args:
        key: The configuration key name (for logging).
        value: The value to validate.
        expected_type: The expected Python type (e.g., float).
        valid_range: Optional (min, max) inclusive range tuple.
        default: The default value to return on validation failure.

    Returns:
        The validated value, or the default if validation fails.
    """
    if not isinstance(value, expected_type):
        # Allow int where float is expected (TOML may parse 90 as int)
        if expected_type is float and isinstance(value, int):
            value = float(value)
        else:
            logger.warning(
                "Configuration key '%s': expected %s, got %s. Using default.",
                key,
                expected_type.__name__,
                type(value).__name__,
            )
            return default

    if valid_range is not None:
        low, high = valid_range
        if not (low <= value <= high):
            logger.warning(
                "Configuration key '%s': value %s is outside range [%s, %s]. Using default.",
                key,
                value,
                low,
                high,
            )
            return default

    return value


def _get_range_for_field(field_name: str) -> tuple[float, float] | None:
    """Return the validation range for a known field, or None."""
    if field_name in _THRESHOLD_FIELDS:
        return _THRESHOLD_RANGE
    if field_name in _WEIGHT_FIELDS:
        return _WEIGHT_RANGE
    return None


def _load_defaults_toml() -> dict[str, Any]:
    """Load the bundled defaults.toml using importlib.resources."""
    ref = importlib.resources.files("opendance.config").joinpath("defaults.toml")
    with importlib.resources.as_file(ref) as defaults_path:
        with open(defaults_path, "rb") as f:
            return tomllib.load(f)


def _load_user_toml(user_path: Path) -> dict[str, Any] | None:
    """Load user config TOML, returning None on missing file or parse error."""
    if not user_path.exists():
        return None

    try:
        with open(user_path, "rb") as f:
            return tomllib.load(f)
    except Exception as exc:
        logger.warning(
            "User configuration file '%s' could not be parsed: %s. Using all defaults.",
            user_path,
            exc,
        )
        return None


def _build_config(merged: dict[str, Any]) -> AppConfig:
    """Construct AppConfig from merged and validated dict."""
    scoring = merged.get("scoring", {})
    thresholds_raw = scoring.get("thresholds", {})
    weights_raw = scoring.get("weights", {})

    # Validate and build ScoringThresholds
    defaults_thresholds = ScoringThresholds()
    threshold_kwargs: dict[str, float] = {}
    for field_name in _THRESHOLD_FIELDS:
        default_val = getattr(defaults_thresholds, field_name)
        if field_name in thresholds_raw:
            validated = validate_value(
                f"scoring.thresholds.{field_name}",
                thresholds_raw[field_name],
                float,
                _get_range_for_field(field_name),
                default_val,
            )
            threshold_kwargs[field_name] = validated
        else:
            threshold_kwargs[field_name] = default_val

    # Validate and build ScoringWeights
    defaults_weights = ScoringWeights()
    weight_kwargs: dict[str, float] = {}
    for field_name in _WEIGHT_FIELDS:
        default_val = getattr(defaults_weights, field_name)
        if field_name in weights_raw:
            validated = validate_value(
                f"scoring.weights.{field_name}",
                weights_raw[field_name],
                float,
                _get_range_for_field(field_name),
                default_val,
            )
            weight_kwargs[field_name] = validated
        else:
            weight_kwargs[field_name] = default_val

    return AppConfig(
        scoring_thresholds=ScoringThresholds(**threshold_kwargs),
        scoring_weights=ScoringWeights(**weight_kwargs),
    )


def load_config(
    defaults_path: Path | None = None,
    user_path: Path | None = None,
) -> AppConfig:
    """Load configuration by merging defaults with optional user overrides.

    1. Locate and parse bundled defaults.toml via importlib.resources
    2. Locate and parse user config.toml (if it exists)
    3. Deep-merge user overrides into defaults
    4. Validate merged values (type and range)
    5. Construct and return AppConfig dataclass

    Args:
        defaults_path: Optional override for the defaults file location (testing).
        user_path: Optional override for the user config file location (testing).

    Returns:
        A validated AppConfig instance.
    """
    # Load defaults
    if defaults_path is not None:
        with open(defaults_path, "rb") as f:
            defaults = tomllib.load(f)
    else:
        defaults = _load_defaults_toml()

    # Load user overrides
    if user_path is None:
        user_path = get_user_config_path()
    user_overrides = _load_user_toml(user_path)

    # Merge
    if user_overrides is not None:
        merged = merge_toml(defaults, user_overrides)
    else:
        merged = defaults

    # Validate and construct
    return _build_config(merged)
