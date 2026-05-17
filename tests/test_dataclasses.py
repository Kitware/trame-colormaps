"""Tests for trame_colormaps.dataclasses.ColormapConfig."""

import pytest
from trame.app import get_server
from vtkmodules.vtkCommonCore import vtkDoubleArray
from vtkmodules.vtkRenderingCore import vtkPolyDataMapper

from trame_colormaps.core.presets import DEFAULT_PRESETS
from trame_colormaps.dataclasses import ColormapConfig

# --- Helpers ---


def _make_data_array(values, name="TestData"):
    """Create a VTK double array from a list of values."""
    arr = vtkDoubleArray()
    arr.SetName(name)
    arr.SetNumberOfTuples(len(values))
    for i, v in enumerate(values):
        arr.SetValue(i, v)
    return arr


# --- Fixtures ---


@pytest.fixture
def config():
    """ColormapConfig with a mapper (required — eager watchers need one)."""
    server = get_server(f"test_dc_{id(object())}")
    mapper = vtkPolyDataMapper()
    data_arr = _make_data_array([0.0, 1.0])
    return ColormapConfig(
        server,
        mapper=mapper,
        data_array_fn=lambda: data_arr,
    )


@pytest.fixture
def wired():
    """ColormapConfig wired to a mapper + data array."""
    server = get_server(f"test_dc_wired_{id(object())}")
    mapper = vtkPolyDataMapper()
    data_arr = _make_data_array([0.0, 50.0, 100.0])
    cfg = ColormapConfig(
        server,
        mapper=mapper,
        data_array_fn=lambda: data_arr,
    )
    cfg.set_data_array("TestData", lambda: data_arr, "point")
    return cfg, mapper, data_arr


# =====================================================================
# Defaults
# =====================================================================


class TestDefaults:
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

    def test_n_ticks_default(self, config):
        assert config.n_ticks == 5

    def test_color_value_min_default(self, config):
        assert config.color_value_min == "0.0"

    def test_color_value_max_default(self, config):
        assert config.color_value_max == "1.0"

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

    def test_active_presets_default_matches(self, config):
        assert config.active_presets == DEFAULT_PRESETS


# =====================================================================
# Mutation
# =====================================================================


class TestMutation:
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


# =====================================================================
# Mapper wiring
# =====================================================================


class TestMapperWiring:
    def test_ctf_on_mapper(self, wired):
        cfg, mapper, _ = wired
        lut = mapper.GetLookupTable()
        assert lut is not None

    def test_scalar_range_from_data(self, wired):
        cfg, mapper, _ = wired
        assert cfg.color_range == (0.0, 100.0)

    def test_range_strings_from_data(self, wired):
        cfg, _, _ = wired
        assert cfg.color_value_min == "0.0"
        assert cfg.color_value_max == "100.0"

    def test_override_range_keeps_manual(self, wired):
        cfg, _, _ = wired
        cfg.color_range = (10.0, 90.0)
        cfg.override_range = True
        cfg.update_color_range()
        assert cfg.color_range == (10.0, 90.0)

    def test_set_data_array_updates_range(self, wired):
        cfg, _, _ = wired
        new_arr = _make_data_array([10.0, 20.0, 30.0])
        cfg.set_data_array("TestData", lambda: new_arr, "cell")
        assert cfg.color_range == (10.0, 30.0)

    def test_mapper_change_increments(self, wired):
        cfg, _, _ = wired
        before = cfg.mapper_change
        cfg.update_color_preset(
            cfg.preset,
            cfg.invert,
            cfg.use_log_scale,
            cfg.discrete_log,
            cfg.n_discrete_colors,
            cfg.n_ticks,
        )
        assert cfg.mapper_change > before


# =====================================================================
# Range string validation (_on_range_str_change)
# =====================================================================


class TestRangeStrValidation:
    def test_valid_strings(self, wired):
        cfg, _, _ = wired
        cfg._on_range_str_change("10.0", "90.0")
        assert cfg.color_value_min_valid is True
        assert cfg.color_value_max_valid is True
        assert cfg.color_range == (10.0, 90.0)

    def test_invalid_min(self, wired):
        cfg, _, _ = wired
        cfg._on_range_str_change("abc", "90.0")
        assert cfg.color_value_min_valid is False
        assert cfg.color_value_max_valid is True

    def test_invalid_max(self, wired):
        cfg, _, _ = wired
        cfg._on_range_str_change("10.0", "xyz")
        assert cfg.color_value_min_valid is True
        assert cfg.color_value_max_valid is False

    def test_both_invalid(self, wired):
        cfg, _, _ = wired
        cfg._on_range_str_change("abc", "xyz")
        assert cfg.color_value_min_valid is False
        assert cfg.color_value_max_valid is False

    def test_nan_string(self, wired):
        cfg, _, _ = wired
        cfg._on_range_str_change("nan", "100")
        assert cfg.color_value_min_valid is False


# =====================================================================
# Preset application (update_color_preset)
# =====================================================================


class TestPresetApplication:
    def test_applies_preset(self, wired):
        cfg, _, _ = wired
        cfg.update_color_preset("Cool to Warm", False, "linear")
        assert cfg.preset == "Cool to Warm"

    def test_generates_lut_images(self, wired):
        cfg, _, _ = wired
        cfg.update_color_preset("Cool to Warm", False, "linear")
        assert cfg.lut_img_h.startswith("data:image/png;base64,")
        assert cfg.lut_img_v.startswith("data:image/png;base64,")

    def test_generates_ticks(self, wired):
        cfg, _, _ = wired
        cfg.update_color_preset("Cool to Warm", False, "linear")
        assert isinstance(cfg.color_ticks, list)

    def test_log_scale(self, wired):
        cfg, _, _ = wired
        cfg.color_range = (1.0, 1000.0)
        cfg.update_color_preset("Cool to Warm", False, "log")
        assert cfg.lut_img_h.startswith("data:image/png;base64,")

    def test_symlog_scale(self, wired):
        cfg, _, _ = wired
        cfg.color_range = (-1000.0, 1000.0)
        cfg.update_color_preset("Cool to Warm", False, "symlog")
        assert cfg.lut_img_h.startswith("data:image/png;base64,")

    def test_discrete_linear(self, wired):
        cfg, _, _ = wired
        cfg.update_color_preset("Cool to Warm", False, "linear", discrete_log=True)
        assert cfg.lut_img_h.startswith("data:image/png;base64,")

    def test_invert_changes_image(self, wired):
        cfg, _, _ = wired
        cfg.update_color_preset("Cool to Warm", False, "linear")
        img_normal = cfg.lut_img_h

        cfg.update_color_preset("Cool to Warm", True, "linear")
        img_inverted = cfg.lut_img_h

        assert img_normal != img_inverted


# =====================================================================
# LUT list building (_build_lut_lists)
# =====================================================================


class TestLutListBuilding:
    def test_builds_lists(self, config):
        config._build_lut_lists(["Cool to Warm", "batlow"])
        assert len(config.luts_normal) > 0
        assert len(config.luts_inverted) > 0

    def test_list_entry_shape(self, config):
        config._build_lut_lists(["Cool to Warm"])
        entry = config.luts_normal[0]
        assert "name" in entry
        assert "url" in entry
        assert "safe" in entry

    def test_sorted_alphabetically(self, config):
        config._build_lut_lists(["Cool to Warm", "batlow", "Viridis (matplotlib)"])
        names = [e["name"] for e in config.luts_normal]
        assert names == sorted(names, key=str.lower)

    def test_empty_list_shows_all(self, config):
        config._build_lut_lists([])
        assert len(config.luts_normal) > 0
