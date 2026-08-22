"""Unit tests for Phase 3 ComparisonConfig and [scoring.comparison].

Tests:
- All default values load correctly
- Partial overrides merge with defaults
- Invalid types fall back to defaults
- Values outside ranges fall back to defaults
- Boundary values accepted
- epsilon > 0 validation
- min_valid_landmarks in [1, 33]
- Existing Phase 1/2 config unchanged
"""

import logging
from pathlib import Path

import pytest

from opendance.config import load_config


class TestComparisonConfigDefaults:
    """Verify all defaults load correctly."""

    def test_pose_scale_factor_default(self) -> None:
        config = load_config()
        assert config.comparison_config.pose_scale_factor == 200.0

    def test_angle_scale_default(self) -> None:
        config = load_config()
        assert config.comparison_config.angle_scale == 1.0

    def test_timing_scale_default(self) -> None:
        config = load_config()
        assert config.comparison_config.timing_scale == 0.5

    def test_min_valid_landmarks_default(self) -> None:
        config = load_config()
        assert config.comparison_config.min_valid_landmarks == 8

    def test_feedback_significance_threshold_default(self) -> None:
        config = load_config()
        assert config.comparison_config.feedback_significance_threshold == 0.1

    def test_motion_speed_weight_default(self) -> None:
        config = load_config()
        assert config.comparison_config.motion_speed_weight == 0.5

    def test_motion_direction_weight_default(self) -> None:
        config = load_config()
        assert config.comparison_config.motion_direction_weight == 0.5

    def test_epsilon_default(self) -> None:
        config = load_config()
        assert config.comparison_config.epsilon == 0.001


class TestComparisonConfigOverrides:
    """Partial overrides merge correctly."""

    def test_override_pose_scale_factor(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\npose_scale_factor = 300.0\n')
        config = load_config(user_path=user)
        assert config.comparison_config.pose_scale_factor == 300.0
        assert config.comparison_config.angle_scale == 1.0  # retained default

    def test_override_min_valid_landmarks(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\nmin_valid_landmarks = 12\n')
        config = load_config(user_path=user)
        assert config.comparison_config.min_valid_landmarks == 12

    def test_override_epsilon(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\nepsilon = 0.01\n')
        config = load_config(user_path=user)
        assert config.comparison_config.epsilon == 0.01

    def test_override_does_not_affect_phase2(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\npose_scale_factor = 500.0\n')
        config = load_config(user_path=user)
        assert config.normalization_config.visibility_threshold == 0.5
        assert config.motion_config.min_velocity_threshold == 0.01


class TestComparisonConfigInvalidValues:
    """Invalid values fall back to defaults with warnings."""

    def test_pose_scale_factor_negative(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\npose_scale_factor = -1.0\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.comparison_config.pose_scale_factor == 200.0

    def test_angle_scale_zero(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\nangle_scale = 0.0\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.comparison_config.angle_scale == 1.0

    def test_min_valid_landmarks_zero(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\nmin_valid_landmarks = 0\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.comparison_config.min_valid_landmarks == 8

    def test_min_valid_landmarks_above_33(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\nmin_valid_landmarks = 50\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.comparison_config.min_valid_landmarks == 8

    def test_epsilon_zero(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\nepsilon = 0.0\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.comparison_config.epsilon == 0.001

    def test_epsilon_negative(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\nepsilon = -0.01\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.comparison_config.epsilon == 0.001

    def test_speed_weight_above_one(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\nmotion_speed_weight = 1.5\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.comparison_config.motion_speed_weight == 0.5

    def test_feedback_threshold_negative(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text(
            '[scoring.comparison]\nfeedback_significance_threshold = -0.1\n'
        )
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.comparison_config.feedback_significance_threshold == 0.1

    def test_wrong_type_string(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\npose_scale_factor = "big"\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.comparison_config.pose_scale_factor == 200.0


class TestComparisonConfigBoundaries:
    """Boundary values accepted."""

    def test_min_valid_landmarks_one(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\nmin_valid_landmarks = 1\n')
        config = load_config(user_path=user)
        assert config.comparison_config.min_valid_landmarks == 1

    def test_min_valid_landmarks_33(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\nmin_valid_landmarks = 33\n')
        config = load_config(user_path=user)
        assert config.comparison_config.min_valid_landmarks == 33

    def test_weights_at_zero(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\nmotion_speed_weight = 0.0\n')
        config = load_config(user_path=user)
        assert config.comparison_config.motion_speed_weight == 0.0

    def test_weights_at_one(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[scoring.comparison]\nmotion_direction_weight = 1.0\n')
        config = load_config(user_path=user)
        assert config.comparison_config.motion_direction_weight == 1.0

    def test_feedback_threshold_at_zero(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text(
            '[scoring.comparison]\nfeedback_significance_threshold = 0.0\n'
        )
        config = load_config(user_path=user)
        assert config.comparison_config.feedback_significance_threshold == 0.0
