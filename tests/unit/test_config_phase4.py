"""Unit tests for Phase 4 PracticeConfig and [practice].

Tests:
- All default values load correctly when [practice] is absent
- Valid overrides merge with defaults
- Invalid/out-of-range values fall back to defaults (per field)
- Boundary values accepted
- Existing Phase 1/2/3 config unchanged
"""

import logging
from pathlib import Path

import pytest

from opendance.config import load_config


class TestPracticeConfigDefaults:
    """Verify defaults are applied when [practice] is absent."""

    def test_render_fps_default(self) -> None:
        config = load_config()
        assert config.practice_config.render_fps == 30.0

    def test_scoring_fps_default(self) -> None:
        config = load_config()
        assert config.practice_config.scoring_fps == 12.0

    def test_silhouette_size_default(self) -> None:
        config = load_config()
        assert config.practice_config.silhouette_size == 250

    def test_defaults_when_practice_section_absent(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text("[camera]\ndevice_index = 1\n")
        config = load_config(user_path=user)
        assert config.practice_config.render_fps == 30.0
        assert config.practice_config.scoring_fps == 12.0
        assert config.practice_config.silhouette_size == 250


class TestPracticeConfigOverrides:
    """Valid overrides are respected."""

    def test_override_render_fps(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text("[practice]\nrender_fps = 60.0\n")
        config = load_config(user_path=user)
        assert config.practice_config.render_fps == 60.0
        assert config.practice_config.scoring_fps == 12.0  # retained default

    def test_override_scoring_fps(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text("[practice]\nscoring_fps = 15.0\n")
        config = load_config(user_path=user)
        assert config.practice_config.scoring_fps == 15.0

    def test_override_silhouette_size(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text("[practice]\nsilhouette_size = 400\n")
        config = load_config(user_path=user)
        assert config.practice_config.silhouette_size == 400

    def test_override_does_not_affect_other_sections(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text("[practice]\nrender_fps = 45.0\n")
        config = load_config(user_path=user)
        assert config.normalization_config.visibility_threshold == 0.5
        assert config.motion_config.min_velocity_threshold == 0.01
        assert config.comparison_config.pose_scale_factor == 200.0


class TestPracticeConfigInvalidValues:
    """Invalid/out-of-range values fall back to defaults with warnings."""

    def test_render_fps_at_lower_bound_excluded(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # render_fps range is (1, 120], so 1.0 is invalid.
        user = tmp_path / "config.toml"
        user.write_text("[practice]\nrender_fps = 1.0\n")
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.practice_config.render_fps == 30.0

    def test_render_fps_above_range(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text("[practice]\nrender_fps = 121.0\n")
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.practice_config.render_fps == 30.0

    def test_scoring_fps_at_lower_bound_excluded(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # scoring_fps range is (1, 60], so 1.0 is invalid.
        user = tmp_path / "config.toml"
        user.write_text("[practice]\nscoring_fps = 1.0\n")
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.practice_config.scoring_fps == 12.0

    def test_scoring_fps_above_range(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text("[practice]\nscoring_fps = 61.0\n")
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.practice_config.scoring_fps == 12.0

    def test_silhouette_size_below_range(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text("[practice]\nsilhouette_size = 49\n")
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.practice_config.silhouette_size == 250

    def test_silhouette_size_above_range(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text("[practice]\nsilhouette_size = 1001\n")
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.practice_config.silhouette_size == 250

    def test_render_fps_wrong_type(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[practice]\nrender_fps = "fast"\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.practice_config.render_fps == 30.0

    def test_scoring_fps_wrong_type(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[practice]\nscoring_fps = "quick"\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.practice_config.scoring_fps == 12.0

    def test_silhouette_size_wrong_type(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[practice]\nsilhouette_size = "big"\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.practice_config.silhouette_size == 250


class TestPracticeConfigBoundaries:
    """Boundary values accepted."""

    def test_render_fps_at_upper_bound(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text("[practice]\nrender_fps = 120.0\n")
        config = load_config(user_path=user)
        assert config.practice_config.render_fps == 120.0

    def test_scoring_fps_at_upper_bound(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text("[practice]\nscoring_fps = 60.0\n")
        config = load_config(user_path=user)
        assert config.practice_config.scoring_fps == 60.0

    def test_silhouette_size_at_lower_bound(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text("[practice]\nsilhouette_size = 50\n")
        config = load_config(user_path=user)
        assert config.practice_config.silhouette_size == 50

    def test_silhouette_size_at_upper_bound(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text("[practice]\nsilhouette_size = 1000\n")
        config = load_config(user_path=user)
        assert config.practice_config.silhouette_size == 1000


class TestPlaybackSpeedsConfig:
    """Verify [practice] playback_speeds / default_playback_speed handling."""

    def test_defaults_when_practice_section_absent(self) -> None:
        config = load_config()
        assert config.practice_config.playback_speeds == (0.5, 0.75, 1.0, 1.25, 1.5)
        assert config.practice_config.default_playback_speed == 1.0

    def test_valid_list_override(self, tmp_path: Path) -> None:
        user = tmp_path / "config.toml"
        user.write_text(
            "[practice]\nplayback_speeds = [0.25, 1.0, 2.0]\n"
            "default_playback_speed = 2.0\n"
        )
        config = load_config(user_path=user)
        assert config.practice_config.playback_speeds == (0.25, 1.0, 2.0)
        assert config.practice_config.default_playback_speed == 2.0

    def test_invalid_entries_filtered(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # 0.1 below range, 5.0 above range, "x" wrong type, true is bool/excluded.
        user = tmp_path / "config.toml"
        user.write_text(
            '[practice]\nplayback_speeds = [0.1, 1.0, 5.0, "x", true, 1.5]\n'
        )
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.practice_config.playback_speeds == (1.0, 1.5)
        # 1.0 is in the filtered list and default defaults to 1.0, so it stays 1.0.
        assert config.practice_config.default_playback_speed == 1.0

    def test_empty_list_falls_back_to_defaults(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text("[practice]\nplayback_speeds = []\n")
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.practice_config.playback_speeds == (0.5, 0.75, 1.0, 1.25, 1.5)

    def test_playback_speeds_wrong_type_falls_back_to_defaults(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        user = tmp_path / "config.toml"
        user.write_text('[practice]\nplayback_speeds = "fast"\n')
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.practice_config.playback_speeds == (0.5, 0.75, 1.0, 1.25, 1.5)

    def test_default_not_in_list_falls_back_to_first(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # 0.75 not in list and 1.0 not in list, so default falls back to first (0.5).
        user = tmp_path / "config.toml"
        user.write_text(
            "[practice]\nplayback_speeds = [0.5, 1.5]\n"
            "default_playback_speed = 0.75\n"
        )
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.practice_config.playback_speeds == (0.5, 1.5)
        assert config.practice_config.default_playback_speed == 0.5

    def test_default_out_of_list_prefers_one_when_present(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # 3.0 out of the list, 1.0 IS present -> default becomes 1.0.
        user = tmp_path / "config.toml"
        user.write_text(
            "[practice]\nplayback_speeds = [0.5, 1.0, 2.0]\n"
            "default_playback_speed = 3.0\n"
        )
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.practice_config.playback_speeds == (0.5, 1.0, 2.0)
        assert config.practice_config.default_playback_speed == 1.0

    def test_out_of_range_default_clamps_to_default(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # 10.0 outside [0.25, 4.0] -> validate_value returns default 1.0; 1.0 in list.
        user = tmp_path / "config.toml"
        user.write_text("[practice]\ndefault_playback_speed = 10.0\n")
        with caplog.at_level(logging.WARNING):
            config = load_config(user_path=user)
        assert config.practice_config.playback_speeds == (0.5, 0.75, 1.0, 1.25, 1.5)
        assert config.practice_config.default_playback_speed == 1.0
