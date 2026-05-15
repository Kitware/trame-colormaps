"""Tests for trame_colormaps.controller.ColormapController."""

import pytest
from trame.app import get_server
from vtkmodules.vtkCommonCore import vtkDoubleArray
from vtkmodules.vtkRenderingCore import vtkDataSetMapper

from trame_colormaps.controller import ColormapController
from trame_colormaps.state import ColormapConfig

# --- Fixtures ---


def _make_data_array(values):
    """Create a VTK double array from a list of values."""
    arr = vtkDoubleArray()
    arr.SetName("TestData")
    arr.SetNumberOfTuples(len(values))
    for i, v in enumerate(values):
        arr.SetValue(i, v)
    return arr


@pytest.fixture
def setup():
    """Create a server, config, mapper, and controller for testing."""
    server = get_server(f"test_ctrl_{id(object())}")
    config = ColormapConfig(server)
    mapper = vtkDataSetMapper()
    data_arr = _make_data_array([0.0, 50.0, 100.0])
    render_called = {"count": 0}

    def data_fn():
        return data_arr

    def render_fn():
        render_called["count"] += 1

    ctrl = ColormapController(
        server=server,
        variable_name="TestData",
        mapper=mapper,
        data_array_fn=data_fn,
        render_fn=render_fn,
        config=config,
    )
    return ctrl, config, mapper, data_arr, render_called


# --- Initialization ---


class TestControllerInit:
    def test_ctf_created(self, setup):
        ctrl, config, mapper, _, _ = setup
        assert ctrl._ctf is not None
        assert ctrl._ctf.GetSize() > 0

    def test_mapper_wired(self, setup):
        ctrl, config, mapper, _, _ = setup
        assert mapper.GetLookupTable() is not None

    def test_config_attached(self, setup):
        ctrl, config, _, _, _ = setup
        assert ctrl.config is config


# --- update_color_range ---


class TestUpdateColorRange:
    def test_range_from_data(self, setup):
        ctrl, config, _, _, _ = setup
        config.override_range = False
        ctrl.update_color_range()
        assert config.color_range == (0.0, 100.0)

    def test_range_updates_strings(self, setup):
        ctrl, config, _, _, _ = setup
        config.override_range = False
        ctrl.update_color_range()
        assert config.color_value_min == "0.0"
        assert config.color_value_max == "100.0"

    def test_override_range_keeps_manual(self, setup):
        ctrl, config, _, _, _ = setup
        config.color_range = (10.0, 90.0)
        config.override_range = True
        ctrl.update_color_range()
        # Should keep the manual range, not replace with data range
        assert config.color_range == (10.0, 90.0)

    def test_render_called(self, setup):
        ctrl, config, _, _, render_called = setup
        initial = render_called["count"]
        ctrl.update_color_range()
        assert render_called["count"] > initial


# --- update_color_preset ---


class TestUpdateColorPreset:
    def test_applies_preset(self, setup):
        ctrl, config, _, _, _ = setup
        ctrl.update_color_preset("Cool to Warm", False, "linear")
        assert config.preset == "Cool to Warm"

    def test_generates_lut_images(self, setup):
        ctrl, config, _, _, _ = setup
        ctrl.update_color_preset("Cool to Warm", False, "linear")
        assert config.lut_img_h.startswith("data:image/png;base64,")
        assert config.lut_img_v.startswith("data:image/png;base64,")

    def test_generates_ticks(self, setup):
        ctrl, config, _, _, _ = setup
        config.color_range = (0.0, 100.0)
        ctrl.update_color_preset("Cool to Warm", False, "linear")
        assert isinstance(config.color_ticks, list)

    def test_log_scale(self, setup):
        ctrl, config, _, _, _ = setup
        config.color_range = (1.0, 1000.0)
        ctrl.update_color_preset("Cool to Warm", False, "log")
        assert config.lut_img_h.startswith("data:image/png;base64,")

    def test_symlog_scale(self, setup):
        ctrl, config, _, _, _ = setup
        config.color_range = (-1000.0, 1000.0)
        ctrl.update_color_preset("Cool to Warm", False, "symlog")
        assert config.lut_img_h.startswith("data:image/png;base64,")

    def test_discrete_linear(self, setup):
        ctrl, config, _, _, _ = setup
        config.color_range = (0.0, 100.0)
        ctrl.update_color_preset("Cool to Warm", False, "linear", discrete_log=True)
        assert config.lut_img_h.startswith("data:image/png;base64,")

    def test_invert(self, setup):
        ctrl, config, _, _, _ = setup
        ctrl.update_color_preset("Cool to Warm", False, "linear")
        img_normal = config.lut_img_h

        ctrl.update_color_preset("Cool to Warm", True, "linear")
        img_inverted = config.lut_img_h

        assert img_normal != img_inverted


# --- set_data_array ---


class TestSetDataArray:
    def test_updates_range(self, setup):
        ctrl, config, _, _, _ = setup
        new_arr = _make_data_array([10.0, 20.0, 30.0])
        ctrl.set_data_array("NewData", lambda: new_arr, scalar_mode="cell")
        assert config.color_range == (10.0, 30.0)

    def test_render_called(self, setup):
        ctrl, config, _, _, render_called = setup
        initial = render_called["count"]
        new_arr = _make_data_array([10.0, 20.0])
        ctrl.set_data_array("NewData", lambda: new_arr)
        assert render_called["count"] > initial


# --- _on_range_str_change ---


class TestOnRangeStrChange:
    def test_valid_strings(self, setup):
        ctrl, config, _, _, _ = setup
        ctrl._on_range_str_change("10.0", "90.0")
        assert config.color_value_min_valid is True
        assert config.color_value_max_valid is True
        assert config.color_range == (10.0, 90.0)

    def test_invalid_min(self, setup):
        ctrl, config, _, _, _ = setup
        ctrl._on_range_str_change("abc", "90.0")
        assert config.color_value_min_valid is False
        assert config.color_value_max_valid is True

    def test_invalid_max(self, setup):
        ctrl, config, _, _, _ = setup
        ctrl._on_range_str_change("10.0", "xyz")
        assert config.color_value_min_valid is True
        assert config.color_value_max_valid is False

    def test_both_invalid(self, setup):
        ctrl, config, _, _, _ = setup
        ctrl._on_range_str_change("abc", "xyz")
        assert config.color_value_min_valid is False
        assert config.color_value_max_valid is False

    def test_nan_string(self, setup):
        ctrl, config, _, _, _ = setup
        ctrl._on_range_str_change("nan", "100")
        assert config.color_value_min_valid is False


# --- _build_lut_lists ---


class TestBuildLutLists:
    def test_builds_lists(self, setup):
        ctrl, config, _, _, _ = setup
        ctrl._build_lut_lists(["Cool to Warm", "batlow"])
        assert len(config.luts_normal) > 0
        assert len(config.luts_inverted) > 0

    def test_list_entry_shape(self, setup):
        ctrl, config, _, _, _ = setup
        ctrl._build_lut_lists(["Cool to Warm"])
        entry = config.luts_normal[0]
        assert "name" in entry
        assert "url" in entry
        assert "safe" in entry

    def test_sorted_alphabetically(self, setup):
        ctrl, config, _, _, _ = setup
        ctrl._build_lut_lists(["Cool to Warm", "batlow", "Viridis (matplotlib)"])
        names = [e["name"] for e in config.luts_normal]
        assert names == sorted(names, key=str.lower)

    def test_empty_list_shows_all(self, setup):
        ctrl, config, _, _, _ = setup
        ctrl._build_lut_lists([])
        assert len(config.luts_normal) > 0
