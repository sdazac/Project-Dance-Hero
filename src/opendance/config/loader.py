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

from opendance.config.models import (
    AppConfig,
    CameraConfig,
    ComparisonConfig,
    MotionConfig,
    NormalizationConfig,
    PoseConfig,
    ReferenceConfig,
    ScoringThresholds,
    ScoringWeights,
)

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

    # Validate and build CameraConfig
    camera_raw = merged.get("camera", {})
    defaults_camera = CameraConfig()
    camera_kwargs: dict[str, Any] = {}

    camera_kwargs["device_index"] = validate_value(
        "camera.device_index",
        camera_raw.get("device_index", defaults_camera.device_index),
        int,
        (0, 1000),
        defaults_camera.device_index,
    )
    camera_kwargs["resolution_width"] = validate_value(
        "camera.resolution_width",
        camera_raw.get("resolution_width", defaults_camera.resolution_width),
        int,
        (1, 10000),
        defaults_camera.resolution_width,
    )
    camera_kwargs["resolution_height"] = validate_value(
        "camera.resolution_height",
        camera_raw.get("resolution_height", defaults_camera.resolution_height),
        int,
        (1, 10000),
        defaults_camera.resolution_height,
    )
    camera_kwargs["consecutive_failure_threshold"] = validate_value(
        "camera.consecutive_failure_threshold",
        camera_raw.get(
            "consecutive_failure_threshold",
            defaults_camera.consecutive_failure_threshold,
        ),
        int,
        (1, 10000),
        defaults_camera.consecutive_failure_threshold,
    )

    # Validate and build PoseConfig
    pose_raw = merged.get("pose", {})
    defaults_pose = PoseConfig()
    pose_kwargs: dict[str, Any] = {}

    model_path_val = pose_raw.get("model_path", defaults_pose.model_path)
    if not isinstance(model_path_val, str) or not model_path_val.strip():
        logger.warning(
            "Configuration key 'pose.model_path': expected non-empty string. Using default."
        )
        model_path_val = defaults_pose.model_path
    pose_kwargs["model_path"] = model_path_val

    pose_kwargs["skeleton_visibility_threshold"] = validate_value(
        "pose.skeleton_visibility_threshold",
        pose_raw.get(
            "skeleton_visibility_threshold",
            defaults_pose.skeleton_visibility_threshold,
        ),
        float,
        (0.0, 1.0),
        defaults_pose.skeleton_visibility_threshold,
    )

    pose_kwargs["max_poses"] = validate_value(
        "pose.max_poses",
        pose_raw.get("max_poses", defaults_pose.max_poses),
        int,
        (1, 10),
        defaults_pose.max_poses,
    )

    # Validate and build NormalizationConfig (Phase 2)
    norm_raw = merged.get("normalization", {})
    defaults_norm = NormalizationConfig()

    norm_enabled = norm_raw.get("enabled", defaults_norm.enabled)
    if not isinstance(norm_enabled, bool):
        logger.warning(
            "Configuration key 'normalization.enabled': expected bool. Using default."
        )
        norm_enabled = defaults_norm.enabled

    norm_vis_threshold = validate_value(
        "normalization.visibility_threshold",
        norm_raw.get("visibility_threshold", defaults_norm.visibility_threshold),
        float,
        (0.0, 1.0),
        defaults_norm.visibility_threshold,
    )
    norm_min_scale = validate_value(
        "normalization.min_body_scale",
        norm_raw.get("min_body_scale", defaults_norm.min_body_scale),
        float,
        (0.0, 100.0),
        defaults_norm.min_body_scale,
    )
    if norm_min_scale <= 0.0:
        logger.warning(
            "Configuration key 'normalization.min_body_scale': must be > 0. Using default."
        )
        norm_min_scale = defaults_norm.min_body_scale

    norm_strategy = norm_raw.get(
        "missing_data_strategy", defaults_norm.missing_data_strategy
    )
    if norm_strategy not in {"leave_none"}:
        logger.warning(
            "Configuration key 'normalization.missing_data_strategy': "
            "invalid value '%s'. Using default.",
            norm_strategy,
        )
        norm_strategy = defaults_norm.missing_data_strategy

    # Validate and build MotionConfig (Phase 2)
    motion_raw = merged.get("motion", {})
    defaults_motion = MotionConfig()

    motion_min_vel = validate_value(
        "motion.min_velocity_threshold",
        motion_raw.get("min_velocity_threshold", defaults_motion.min_velocity_threshold),
        float,
        (0.0, 1000.0),
        defaults_motion.min_velocity_threshold,
    )

    # Validate and build ReferenceConfig (Phase 2)
    ref_raw = merged.get("reference", {})
    defaults_ref = ReferenceConfig()

    ref_cache_dir = ref_raw.get("cache_directory", defaults_ref.cache_directory)
    if not isinstance(ref_cache_dir, str):
        logger.warning(
            "Configuration key 'reference.cache_directory': expected string. Using default."
        )
        ref_cache_dir = defaults_ref.cache_directory

    ref_auto_cache = ref_raw.get("auto_cache", defaults_ref.auto_cache)
    if not isinstance(ref_auto_cache, bool):
        logger.warning(
            "Configuration key 'reference.auto_cache': expected bool. Using default."
        )
        ref_auto_cache = defaults_ref.auto_cache

    ref_sample_fps = validate_value(
        "reference.sample_fps",
        ref_raw.get("sample_fps", defaults_ref.sample_fps),
        float,
        (0.001, 1000.0),
        defaults_ref.sample_fps,
    )

    # Validate and build ComparisonConfig (Phase 3)
    scoring_raw = merged.get("scoring", {})
    comp_raw = scoring_raw.get("comparison", {})
    defaults_comp = ComparisonConfig()

    comp_pose_scale = validate_value(
        "scoring.comparison.pose_scale_factor",
        comp_raw.get("pose_scale_factor", defaults_comp.pose_scale_factor),
        float,
        (0.001, 100000.0),
        defaults_comp.pose_scale_factor,
    )
    comp_angle_scale = validate_value(
        "scoring.comparison.angle_scale",
        comp_raw.get("angle_scale", defaults_comp.angle_scale),
        float,
        (0.001, 100000.0),
        defaults_comp.angle_scale,
    )
    comp_timing_scale = validate_value(
        "scoring.comparison.timing_scale",
        comp_raw.get("timing_scale", defaults_comp.timing_scale),
        float,
        (0.001, 100000.0),
        defaults_comp.timing_scale,
    )
    comp_min_landmarks = validate_value(
        "scoring.comparison.min_valid_landmarks",
        comp_raw.get("min_valid_landmarks", defaults_comp.min_valid_landmarks),
        int,
        (1, 33),
        defaults_comp.min_valid_landmarks,
    )
    comp_feedback_thresh = validate_value(
        "scoring.comparison.feedback_significance_threshold",
        comp_raw.get(
            "feedback_significance_threshold",
            defaults_comp.feedback_significance_threshold,
        ),
        float,
        (0.0, 1.0),
        defaults_comp.feedback_significance_threshold,
    )
    comp_speed_weight = validate_value(
        "scoring.comparison.motion_speed_weight",
        comp_raw.get("motion_speed_weight", defaults_comp.motion_speed_weight),
        float,
        (0.0, 1.0),
        defaults_comp.motion_speed_weight,
    )
    comp_dir_weight = validate_value(
        "scoring.comparison.motion_direction_weight",
        comp_raw.get("motion_direction_weight", defaults_comp.motion_direction_weight),
        float,
        (0.0, 1.0),
        defaults_comp.motion_direction_weight,
    )
    comp_epsilon = validate_value(
        "scoring.comparison.epsilon",
        comp_raw.get("epsilon", defaults_comp.epsilon),
        float,
        (0.0, 1.0),
        defaults_comp.epsilon,
    )
    if comp_epsilon <= 0.0:
        logger.warning(
            "Configuration key 'scoring.comparison.epsilon': must be > 0. Using default."
        )
        comp_epsilon = defaults_comp.epsilon

    return AppConfig(
        scoring_thresholds=ScoringThresholds(**threshold_kwargs),
        scoring_weights=ScoringWeights(**weight_kwargs),
        camera_config=CameraConfig(**camera_kwargs),
        pose_config=PoseConfig(**pose_kwargs),
        normalization_config=NormalizationConfig(
            enabled=norm_enabled,
            visibility_threshold=norm_vis_threshold,
            min_body_scale=norm_min_scale,
            missing_data_strategy=norm_strategy,
        ),
        motion_config=MotionConfig(
            min_velocity_threshold=motion_min_vel,
        ),
        reference_config=ReferenceConfig(
            cache_directory=ref_cache_dir,
            auto_cache=ref_auto_cache,
            sample_fps=ref_sample_fps,
        ),
        comparison_config=ComparisonConfig(
            pose_scale_factor=comp_pose_scale,
            angle_scale=comp_angle_scale,
            timing_scale=comp_timing_scale,
            min_valid_landmarks=comp_min_landmarks,
            feedback_significance_threshold=comp_feedback_thresh,
            motion_speed_weight=comp_speed_weight,
            motion_direction_weight=comp_dir_weight,
            epsilon=comp_epsilon,
        ),
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
