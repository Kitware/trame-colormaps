"""Tests for trame_colormaps.state.ColormapConfig defaults and field types."""

import pytest
from trame.app import get_server

from trame_colormaps.core.presets import DEFAULT_PRESETS
from trame_colormaps.state import ColormapConfig


@pytest.fixture
def config():
    """Create a ColormapConfig with a fresh trame server."""
    server = get_server(f"test_state_{id(object())}")
    return ColormapConfig(server)


class TestColormapConfigDefaults:
    def test_preset_default(self, config):
        assert config.preset == "BuGnYl"

    def test_invert_default(self, config):
        assert config.invert is False

    def test_color_blind_default(self, config):
        assert config.color_blind is False

    def test_use_log_scale_default(self, config):
        assert config.use_log_scale == "linear"

    def test_discrete_log_default(self, config):
        assert config.discrete_log is False

    def test_n_discrete_colors_default(self, config):
        assert config.n_discrete_colors == 4

    def test_n_intervals_default(self, config):
        assert config.n_intervals == 4

    def test_n_ticks_default(self, config):
        assert config.n_ticks == 5

    def test_color_value_min_default(self, config):
        assert config.color_value_min == "0"

    def test_color_value_max_default(self, config):
        assert config.color_value_max == "1"

    def test_override_range_default(self, config):
        assert config.override_range is False

    def test_color_range_default(self, config):
        assert config.color_range == (0, 1)

    def test_n_colors_default(self, config):
        assert config.n_colors == 255

    def test_menu_default(self, config):
        assert config.menu is False

    def test_orientation_default(self, config):
        assert config.orientation == "horizontal"

    def test_validation_defaults(self, config):
        assert config.color_value_min_valid is True
        assert config.color_value_max_valid is True


class TestColormapConfigMutation:
    def test_set_preset(self, config):
        config.preset = "Cool to Warm"
        assert config.preset == "Cool to Warm"

    def test_set_invert(self, config):
        config.invert = True
        assert config.invert is True

    def test_set_log_scale(self, config):
        config.use_log_scale = "log"
        assert config.use_log_scale == "log"

    def test_set_color_range(self, config):
        config.color_range = (10.0, 100.0)
        assert config.color_range == (10.0, 100.0)

    def test_set_override_range(self, config):
        config.override_range = True
        assert config.override_range is True

    def test_active_presets_default_matches(self, config):
        assert config.active_presets == DEFAULT_PRESETS
