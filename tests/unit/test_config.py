"""Unit tests for the OpenDance AI configuration system.

Tests cover:
- Default loading (thresholds + weights match bundled TOML)
- Partial user override merge behavior
- Invalid type and out-of-range value handling
- Validation range boundaries
- Weight-sum not validated
- Malformed TOML fallback
- Missing user config
- Platform-specific user config path resolution (mocked)
"""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from opendance.config import load_config
from opendance.config.loader import get_user_config_path, merge_toml


class TestConfigDefaults:
    """Test that defaults.toml produces expected AppConfig values."""

    def test_default_thresholds(self) -> None:
        config = load_config()
        assert config.scoring_thresholds.perfect_min == 90.0
        assert config.scoring_thresholds.great_min == 75.0
        assert config.scoring_thresholds.ok_min == 50.0
        assert config.scoring_thresholds.meh_min == 30.0

    def test_default_weights(self) -> None:
        config = load_config()
        assert config.scoring_weights.pose_similarity == 0.40
        assert config.scoring_weights.angle_similarity == 0.25
        assert config.scoring_weights.motion_similarity == 0.20
        assert config.scoring_weights.timing_similarity == 0.15


class TestConfigMerge:
    """Test partial user override merge behavior."""

    def test_partial_threshold_override(self, tmp_path: Path) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[scoring.thresholds]\nperfect_min = 95.0\n')
        config = load_config(user_path=user_toml)
        assert config.scoring_thresholds.perfect_min == 95.0
        assert config.scoring_thresholds.great_min == 75.0
        assert config.scoring_thresholds.ok_min == 50.0
        assert config.scoring_thresholds.meh_min == 30.0

    def test_partial_weight_override(self, tmp_path: Path) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[scoring.weights]\npose_similarity = 0.50\n')
        config = load_config(user_path=user_toml)
        assert config.scoring_weights.pose_similarity == 0.50
        assert config.scoring_weights.angle_similarity == 0.25
        assert config.scoring_weights.motion_similarity == 0.20
        assert config.scoring_weights.timing_similarity == 0.15

    def test_merge_toml_deep(self) -> None:
        defaults = {"scoring": {"thresholds": {"perfect_min": 90.0, "great_min": 75.0}}}
        overrides = {"scoring": {"thresholds": {"perfect_min": 95.0}}}
        merged = merge_toml(defaults, overrides)
        assert merged["scoring"]["thresholds"]["perfect_min"] == 95.0
        assert merged["scoring"]["thresholds"]["great_min"] == 75.0


class TestConfigValidation:
    """Test invalid values fall back to defaults with warnings."""

    def test_wrong_type_string_for_float(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[scoring.thresholds]\nperfect_min = "not_a_number"\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user_toml)
        assert config.scoring_thresholds.perfect_min == 90.0
        assert any("perfect_min" in r.message for r in caplog.records)

    def test_threshold_out_of_range_above(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[scoring.thresholds]\nperfect_min = 150.0\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user_toml)
        assert config.scoring_thresholds.perfect_min == 90.0
        assert any("perfect_min" in r.message for r in caplog.records)

    def test_threshold_out_of_range_below(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[scoring.thresholds]\nmeh_min = -5.0\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user_toml)
        assert config.scoring_thresholds.meh_min == 30.0

    def test_weight_out_of_range_above(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[scoring.weights]\npose_similarity = 1.5\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user_toml)
        assert config.scoring_weights.pose_similarity == 0.40

    def test_weight_out_of_range_below(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[scoring.weights]\npose_similarity = -0.5\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user_toml)
        assert config.scoring_weights.pose_similarity == 0.40


class TestConfigValidationBoundaries:
    """Test boundary values are accepted (0.0, 100.0, 1.0)."""

    def test_threshold_at_zero(self, tmp_path: Path) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[scoring.thresholds]\nmeh_min = 0.0\n')
        config = load_config(user_path=user_toml)
        assert config.scoring_thresholds.meh_min == 0.0

    def test_threshold_at_hundred(self, tmp_path: Path) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[scoring.thresholds]\nperfect_min = 100.0\n')
        config = load_config(user_path=user_toml)
        assert config.scoring_thresholds.perfect_min == 100.0

    def test_weight_at_zero(self, tmp_path: Path) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[scoring.weights]\ntiming_similarity = 0.0\n')
        config = load_config(user_path=user_toml)
        assert config.scoring_weights.timing_similarity == 0.0

    def test_weight_at_one(self, tmp_path: Path) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('[scoring.weights]\npose_similarity = 1.0\n')
        config = load_config(user_path=user_toml)
        assert config.scoring_weights.pose_similarity == 1.0


class TestWeightSumNotValidated:
    """Test that weight-sum is NOT validated (individual valid weights accepted)."""

    def test_all_weights_090_accepted(self, tmp_path: Path) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text(
            '[scoring.weights]\n'
            'pose_similarity = 0.90\n'
            'angle_similarity = 0.90\n'
            'motion_similarity = 0.90\n'
            'timing_similarity = 0.90\n'
        )
        config = load_config(user_path=user_toml)
        assert config.scoring_weights.pose_similarity == 0.90
        assert config.scoring_weights.angle_similarity == 0.90
        assert config.scoring_weights.motion_similarity == 0.90
        assert config.scoring_weights.timing_similarity == 0.90


class TestMalformedToml:
    """Test malformed TOML falls back to all defaults with warning."""

    def test_malformed_toml_uses_defaults(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user_toml = tmp_path / "config.toml"
        user_toml.write_text('this is [[[not valid toml')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user_toml)
        assert config.scoring_thresholds.perfect_min == 90.0
        assert config.scoring_weights.pose_similarity == 0.40
        assert any("could not be parsed" in r.message.lower() for r in caplog.records)


class TestMissingUserConfig:
    """Test missing user config loads defaults without error."""

    def test_nonexistent_user_config(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist.toml"
        config = load_config(user_path=nonexistent)
        assert config.scoring_thresholds.perfect_min == 90.0
        assert config.scoring_weights.pose_similarity == 0.40


class TestUserConfigPath:
    """Test get_user_config_path() on Windows and non-Windows (mocked)."""

    def test_windows_path_uses_appdata(self) -> None:
        with patch("opendance.config.loader.sys.platform", "win32"), \
             patch.dict("os.environ", {"APPDATA": r"C:\Users\Test\AppData\Roaming"}):
            path = get_user_config_path()
        assert path == Path(r"C:\Users\Test\AppData\Roaming\opendance\config.toml")

    def test_non_windows_path_uses_home_config(self) -> None:
        with patch("opendance.config.loader.sys.platform", "linux"), \
             patch(
                 "opendance.config.loader.Path.home",
                 return_value=Path("/home/testuser"),
             ):
            path = get_user_config_path()
        assert path == Path("/home/testuser/.config/opendance/config.toml")
