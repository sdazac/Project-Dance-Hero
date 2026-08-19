"""Unit tests for Phase 2 configuration extensions.

Tests: NormalizationConfig, MotionConfig, ReferenceConfig defaults,
partial overrides, invalid values, and merge behavior.
"""

import logging
from pathlib import Path

import pytest

from opendance.config import load_config


class TestPhase2ConfigDefaults:
    """Test that defaults.toml produces expected Phase 2 values."""

    def test_normalization_defaults(self) -> None:
        config = load_config()
        nc = config.normalization_config
        assert nc.enabled is False
        assert nc.visibility_threshold == 0.5
        assert nc.min_body_scale == 0.001
        assert nc.missing_data_strategy == "leave_none"

    def test_motion_defaults(self) -> None:
        config = load_config()
        mc = config.motion_config
        assert mc.min_velocity_threshold == 0.01

    def test_reference_defaults(self) -> None:
        config = load_config()
        rc = config.reference_config
        assert rc.cache_directory == ""
        assert rc.auto_cache is False
        assert rc.sample_fps == 30.0

    def test_phase1_config_unchanged(self) -> None:
        """Phase 1 config values remain intact after Phase 2 extension."""
        config = load_config()
        assert config.camera_config.device_index == 0
        assert config.pose_config.skeleton_visibility_threshold == 0.5
        assert config.scoring_thresholds.perfect_min == 90.0


class TestPhase2ConfigOverrides:
    """Test partial user overrides merge correctly."""

    def test_normalization_partial_override(self, tmp_path: Path) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text(
            '[normalization]\nenabled = true\nvisibility_threshold = 0.7\n'
        )
        config = load_config(user_path=user_toml)
        nc = config.normalization_config
        assert nc.enabled is True
        assert nc.visibility_threshold == 0.7
        assert nc.min_body_scale == 0.001  # retained default
        assert nc.missing_data_strategy == "leave_none"  # retained default

    def test_motion_override(self, tmp_path: Path) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[motion]\nmin_velocity_threshold = 0.05\n')
        config = load_config(user_path=user_toml)
        assert config.motion_config.min_velocity_threshold == 0.05

    def test_reference_partial_override(self, tmp_path: Path) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text(
            '[reference]\nauto_cache = true\nsample_fps = 60.0\n'
        )
        config = load_config(user_path=user_toml)
        rc = config.reference_config
        assert rc.auto_cache is True
        assert rc.sample_fps == 60.0
        assert rc.cache_directory == ""  # retained default

    def test_override_does_not_affect_phase1(self, tmp_path: Path) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[normalization]\nenabled = true\n')
        config = load_config(user_path=user_toml)
        assert config.camera_config.device_index == 0
        assert config.pose_config.model_path == "assets/models/pose_landmarker.task"


class TestPhase2ConfigValidation:
    """Test invalid values fall back to defaults with warnings."""

    def test_visibility_threshold_out_of_range(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[normalization]\nvisibility_threshold = 2.0\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user_toml)
        assert config.normalization_config.visibility_threshold == 0.5
        assert any("visibility_threshold" in r.message for r in caplog.records)

    def test_min_body_scale_zero(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[normalization]\nmin_body_scale = 0.0\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user_toml)
        assert config.normalization_config.min_body_scale == 0.001

    def test_invalid_missing_data_strategy(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[normalization]\nmissing_data_strategy = "interpolate"\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user_toml)
        assert config.normalization_config.missing_data_strategy == "leave_none"

    def test_enabled_wrong_type(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[normalization]\nenabled = "yes"\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user_toml)
        assert config.normalization_config.enabled is False

    def test_min_velocity_negative(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[motion]\nmin_velocity_threshold = -1.0\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user_toml)
        assert config.motion_config.min_velocity_threshold == 0.01

    def test_sample_fps_zero(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[reference]\nsample_fps = 0.0\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user_toml)
        assert config.reference_config.sample_fps == 30.0

    def test_auto_cache_wrong_type(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[reference]\nauto_cache = "yes"\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user_toml)
        assert config.reference_config.auto_cache is False

    def test_cache_directory_wrong_type(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[reference]\ncache_directory = 123\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user_toml)
        assert config.reference_config.cache_directory == ""


class TestPhase2ConfigBoundaries:
    """Test valid boundary values are accepted."""

    def test_visibility_threshold_at_zero(self, tmp_path: Path) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[normalization]\nvisibility_threshold = 0.0\n')
        config = load_config(user_path=user_toml)
        assert config.normalization_config.visibility_threshold == 0.0

    def test_visibility_threshold_at_one(self, tmp_path: Path) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[normalization]\nvisibility_threshold = 1.0\n')
        config = load_config(user_path=user_toml)
        assert config.normalization_config.visibility_threshold == 1.0

    def test_sample_fps_small_valid(self, tmp_path: Path) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[reference]\nsample_fps = 1.0\n')
        config = load_config(user_path=user_toml)
        assert config.reference_config.sample_fps == 1.0
