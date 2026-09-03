"""Tests for trame_colormaps.dataclasses.ColormapConfig."""

import pytest
from trame.app import get_server
from vtkmodules.vtkCommonCore import vtkDoubleArray
from vtkmodules.vtkRenderingCore import vtkPolyDataMapper

from trame_colormaps.core.presets import (
    CYCLIC_PRESETS,
    DEFAULT_PRESETS,
    DIVERGING_PRESETS,
    MULTI_SEQUENTIAL_PRESETS,
    SEQUENTIAL_PRESETS,
)
from trame_colormaps.dataclasses import ColormapConfig

# --- Helpers ---
# In production, trame's reactive event loop fires @watch handlers
# automatically when a field changes.  Tests run without that loop,
# so we must set the field *and* call the handler ourselves.


def _enter_diverging(cfg):
    """Simulate toggling diverging on: set the field and call the handler."""
    cfg.diverging = True
    cfg._on_diverging_change(True)


def _leave_diverging(cfg):
    """Simulate toggling diverging off: set the field and call the handler."""
    cfg.diverging = False
    cfg._on_diverging_change(False)


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

    def test_nan_color_default(self, config):
        assert config.nan_color == [0.0, 0.0, 0.0, 0.0]

    def test_show_nan_menu_default(self, config):
        assert config.show_nan_menu is False

    def test_cut_outside_range_default(self, config):
        assert config.cut_outside_range is False


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


# =====================================================================
# Diverging mode
# =====================================================================


class TestDivergingDefaults:
    def test_diverging_default(self, config):
        assert config.diverging is False

    def test_epsilon_default(self, config):
        assert config.epsilon == "0"

    def test_epsilon_valid_default(self, config):
        assert config.epsilon_valid is True


class TestDivergingPresets:
    def test_diverging_presets_not_empty(self):
        assert len(DIVERGING_PRESETS) > 0

    def test_cool_to_warm_is_diverging(self):
        assert "Cool to Warm" in DIVERGING_PRESETS

    def test_bam_is_diverging(self):
        assert "bam" in DIVERGING_PRESETS

    def test_brewer_diverging_included(self):
        brewer = [n for n in DIVERGING_PRESETS if "Brewer Diverging" in n]
        assert len(brewer) > 0

    def test_blue_orange_divergent_included(self):
        assert "Blue Orange (divergent)" in DIVERGING_PRESETS


class TestDivergingMode:
    """Test diverging mode enter/leave behavior.

    Uses _enter_diverging / _leave_diverging helpers that set the field
    and call the handler together, matching real runtime behavior.
    """

    @pytest.fixture
    def div_cfg(self):
        """ColormapConfig with asymmetric data for diverging tests."""
        server = get_server(f"test_div_{id(object())}")
        mapper = vtkPolyDataMapper()
        data_arr = _make_data_array([-30.0, 10.0, 50.0])
        cfg = ColormapConfig(
            server,
            mapper=mapper,
            data_array_fn=lambda: data_arr,
        )
        cfg.set_data_array("TestData", lambda: data_arr, "point")
        return cfg

    def test_entering_diverging_filters_presets(self, div_cfg):
        _enter_diverging(div_cfg)
        for name in div_cfg.active_presets:
            assert name in DIVERGING_PRESETS, f"{name} is not a diverging preset"

    def test_entering_diverging_enables_override_range(self, div_cfg):
        _enter_diverging(div_cfg)
        assert div_cfg.override_range is True

    def test_entering_diverging_makes_range_symmetric(self, div_cfg):
        _enter_diverging(div_cfg)
        vmin, vmax = div_cfg.color_range
        assert vmin == -vmax
        assert vmax > 0

    def test_symmetric_range_uses_max_abs(self, div_cfg):
        # data is [-30, 10, 50], so abs_max = 50
        _enter_diverging(div_cfg)
        _, vmax = div_cfg.color_range
        assert vmax == 50.0

    def test_diverging_forces_log_to_linear(self, div_cfg):
        div_cfg.use_log_scale = "log"
        _enter_diverging(div_cfg)
        assert div_cfg.use_log_scale == "linear"

    def test_diverging_keeps_symlog(self, div_cfg):
        div_cfg.use_log_scale = "symlog"
        _enter_diverging(div_cfg)
        assert div_cfg.use_log_scale == "symlog"

    def test_diverging_keeps_linear(self, div_cfg):
        div_cfg.use_log_scale = "linear"
        _enter_diverging(div_cfg)
        assert div_cfg.use_log_scale == "linear"

    def test_diverging_switches_to_diverging_preset(self, div_cfg):
        _enter_diverging(div_cfg)
        assert div_cfg.preset in DIVERGING_PRESETS

    def test_leaving_diverging_restores_category_presets(self, div_cfg):
        _enter_diverging(div_cfg)
        # While diverging, only diverging presets are active
        for p in div_cfg.active_presets:
            assert p in DIVERGING_PRESETS
        _leave_diverging(div_cfg)
        # After leaving, presets rebuilt from selected_categories
        assert len(div_cfg.active_presets) > len(DIVERGING_PRESETS)

    def test_leaving_diverging_restores_log_scale(self, div_cfg):
        div_cfg.use_log_scale = "log"
        _enter_diverging(div_cfg)
        assert div_cfg.use_log_scale == "linear"
        _leave_diverging(div_cfg)
        assert div_cfg.use_log_scale == "log"


class TestEpsilon:
    """Test _on_epsilon_change and _apply_symmetric_range by calling directly."""

    @pytest.fixture
    def eps_cfg(self):
        server = get_server(f"test_eps_{id(object())}")
        mapper = vtkPolyDataMapper()
        data_arr = _make_data_array([-20.0, 0.0, 30.0])
        cfg = ColormapConfig(
            server,
            mapper=mapper,
            data_array_fn=lambda: data_arr,
        )
        cfg.set_data_array("TestData", lambda: data_arr, "point")
        return cfg

    def test_epsilon_does_not_change_range(self, eps_cfg):
        _enter_diverging(eps_cfg)
        # abs_max populated from data: max(|-20|,|30|) = 30
        assert eps_cfg.abs_max == "30.0"
        assert eps_cfg.color_range == (-30.0, 30.0)
        eps_cfg.epsilon = "5"
        eps_cfg._on_epsilon_change("5")
        # Range stays the same — epsilon modifies CTF, not range
        assert eps_cfg.color_range == (-30.0, 30.0)

    def test_epsilon_injects_band_in_ctf(self, eps_cfg):
        _enter_diverging(eps_cfg)
        eps_cfg.epsilon = "5"
        eps_cfg._on_epsilon_change("5")
        # Check that the CTF has control points at -5, 0, +5
        from trame_colormaps.core.presets import get_rgb_points

        pts = get_rgb_points(eps_cfg._ctf)
        xs = [pts[i] for i in range(0, len(pts), 4)]
        assert -5.0 in xs
        assert 0.0 in xs
        assert 5.0 in xs

    def test_epsilon_invalid_keeps_old_ctf(self, eps_cfg):
        _enter_diverging(eps_cfg)
        eps_cfg.epsilon = "abc"
        eps_cfg._on_epsilon_change("abc")
        assert eps_cfg.epsilon_valid is False

    def test_epsilon_negative_invalid(self, eps_cfg):
        _enter_diverging(eps_cfg)
        eps_cfg.epsilon = "-1"
        eps_cfg._on_epsilon_change("-1")
        assert eps_cfg.epsilon_valid is False

    def test_abs_max_clamps_range(self, eps_cfg):
        _enter_diverging(eps_cfg)
        # User clamps to 10 (ignoring actual data range of 30)
        eps_cfg.abs_max = "10"
        eps_cfg._on_abs_max_change("10")
        assert eps_cfg.color_range == (-10.0, 10.0)


class TestCategoryFiltering:
    """Tests for category-based preset filtering."""

    @pytest.fixture
    def cat_cfg(self):
        server = get_server(f"test_cat_{id(object())}")
        mapper = vtkPolyDataMapper()
        arr = _make_data_array([0, 50, 100])
        cfg = ColormapConfig(server, mapper=mapper, data_array_fn=lambda: arr)
        cfg.update_color_range()
        return cfg

    def test_default_category_is_sequential(self, cat_cfg):
        assert cat_cfg.selected_categories == "sequential"

    def test_selecting_diverging_filters_presets(self, cat_cfg):
        cat_cfg.selected_categories = "diverging"
        cat_cfg._on_categories_change("diverging")
        for p in cat_cfg.active_presets:
            assert p in DIVERGING_PRESETS

    def test_selecting_sequential_filters_presets(self, cat_cfg):
        cat_cfg.selected_categories = "sequential"
        cat_cfg._on_categories_change("sequential")
        for p in cat_cfg.active_presets:
            assert p in SEQUENTIAL_PRESETS

    def test_selecting_cyclic_filters_presets(self, cat_cfg):
        cat_cfg.selected_categories = "cyclic"
        cat_cfg._on_categories_change("cyclic")
        for p in cat_cfg.active_presets:
            assert p in CYCLIC_PRESETS

    def test_selecting_multi_sequential_filters_presets(self, cat_cfg):
        cat_cfg.selected_categories = "multi-sequential"
        cat_cfg._on_categories_change("multi-sequential")
        for p in cat_cfg.active_presets:
            assert p in MULTI_SEQUENTIAL_PRESETS

    def test_invalid_category_falls_back_to_defaults(self, cat_cfg):
        cat_cfg.selected_categories = "nonexistent"
        cat_cfg._on_categories_change("nonexistent")
        assert cat_cfg.active_presets == sorted(DEFAULT_PRESETS)

    def test_leaving_diverging_resets_to_sequential(self, cat_cfg):
        cat_cfg.selected_categories = "cyclic"
        _enter_diverging(cat_cfg)
        _leave_diverging(cat_cfg)
        assert cat_cfg.selected_categories == "sequential"
        for p in cat_cfg.active_presets:
            assert p in SEQUENTIAL_PRESETS

    def test_show_categories_default_false(self, cat_cfg):
        assert cat_cfg.show_categories is False


class TestPresetSets:
    """Tests for the module-level preset category sets."""

    def test_sequential_not_empty(self):
        assert len(SEQUENTIAL_PRESETS) > 0

    def test_multi_sequential_not_empty(self):
        assert len(MULTI_SEQUENTIAL_PRESETS) > 0

    def test_diverging_not_empty(self):
        assert len(DIVERGING_PRESETS) > 0

    def test_cyclic_not_empty(self):
        assert len(CYCLIC_PRESETS) > 0

    def test_no_overlap_sequential_diverging(self):
        assert not (SEQUENTIAL_PRESETS & DIVERGING_PRESETS)

    def test_no_overlap_sequential_multi_sequential(self):
        assert not (SEQUENTIAL_PRESETS & MULTI_SEQUENTIAL_PRESETS)

    def test_no_overlap_diverging_cyclic(self):
        assert not (DIVERGING_PRESETS & CYCLIC_PRESETS)


# =====================================================================
# NaN Color
# =====================================================================


class TestNanColor:
    def test_apply_nan_color_sets_lut(self, config):
        config._build_lut_from_ctf(config._ctf)
        config.nan_color = [1.0, 0.0, 1.0, 1.0]
        config._apply_nan_color()
        assert config._lut.GetNanColor() == pytest.approx((1.0, 0.0, 1.0, 1.0))

    def test_apply_nan_color_transparent(self, config):
        config._build_lut_from_ctf(config._ctf)
        config.nan_color = [0.0, 0.0, 0.0, 0.0]
        config._apply_nan_color()
        assert config._lut.GetNanColor() == pytest.approx((0.0, 0.0, 0.0, 0.0))

    def test_apply_nan_color_handles_short_list(self, config):
        config._build_lut_from_ctf(config._ctf)
        config.nan_color = [1.0, 0.0]
        config._apply_nan_color()
        assert config._lut.GetNanColor() == pytest.approx((0.0, 0.0, 0.0, 0.0))

    def test_apply_nan_color_handles_none(self, config):
        config._build_lut_from_ctf(config._ctf)
        config.nan_color = None
        config._apply_nan_color()
        assert config._lut.GetNanColor() == pytest.approx((0.0, 0.0, 0.0, 0.0))

    def test_apply_nan_color_noop_without_lut(self, config):
        config._lut = None
        config.nan_color = [1.0, 0.0, 0.0, 0.5]
        config._apply_nan_color()  # should not raise


# =====================================================================
# Cut Outside Range
# =====================================================================


class TestCutOutsideRange:
    def test_cut_enables_above_below_range(self, config):
        config._build_lut_from_ctf(config._ctf)
        config.nan_color = [1.0, 0.0, 1.0, 1.0]
        config.cut_outside_range = True
        config._apply_nan_color()
        assert config._lut.GetUseAboveRangeColor() == 1
        assert config._lut.GetUseBelowRangeColor() == 1
        assert config._lut.GetAboveRangeColor() == pytest.approx((1.0, 0.0, 1.0, 1.0))
        assert config._lut.GetBelowRangeColor() == pytest.approx((1.0, 0.0, 1.0, 1.0))

    def test_clamp_disables_above_below_range(self, config):
        config._build_lut_from_ctf(config._ctf)
        config.cut_outside_range = False
        config._apply_nan_color()
        assert config._lut.GetUseAboveRangeColor() == 0
        assert config._lut.GetUseBelowRangeColor() == 0

    def test_cut_uses_nan_color(self, config):
        config._build_lut_from_ctf(config._ctf)
        config.nan_color = [0.0, 1.0, 0.0, 0.5]
        config.cut_outside_range = True
        config._apply_nan_color()
        assert config._lut.GetAboveRangeColor() == pytest.approx((0.0, 1.0, 0.0, 0.5))
        assert config._lut.GetBelowRangeColor() == pytest.approx((0.0, 1.0, 0.0, 0.5))


# =====================================================================
# LUT Rendering (vtkLookupTable)
# =====================================================================


class TestLutRendering:
    def test_build_lut_from_ctf_creates_lut(self, config):
        from vtkmodules.vtkCommonCore import vtkLookupTable

        config._build_lut_from_ctf(config._ctf)
        assert config._lut is not None
        assert isinstance(config._lut, vtkLookupTable)

    def test_build_lut_from_ctf_sets_mapper_lut(self, config):
        config._build_lut_from_ctf(config._ctf)
        assert next(iter(config._mappers)).GetLookupTable() is config._lut

    def test_lut_table_values_have_alpha_one(self, config):
        config._build_lut_from_ctf(config._ctf)
        n = config._lut.GetNumberOfTableValues()
        for i in range(n):
            rgba = config._lut.GetTableValue(i)
            assert rgba[3] == pytest.approx(1.0), f"Entry {i} alpha={rgba[3]}"

    def test_lut_nan_color_has_alpha_zero(self, config):
        config._build_lut_from_ctf(config._ctf)
        config.nan_color = [0.0, 0.0, 0.0, 0.0]
        config._apply_nan_color()
        assert config._lut.GetNanColor() == pytest.approx((0.0, 0.0, 0.0, 0.0))

    def test_lut_nan_color_custom_rgba(self, config):
        config._build_lut_from_ctf(config._ctf)
        config.nan_color = [1.0, 0.0, 1.0, 0.5]
        config._apply_nan_color()
        assert config._lut.GetNanColor() == pytest.approx((1.0, 0.0, 1.0, 0.5))

    def test_lut_above_below_range_has_alpha(self, config):
        config._build_lut_from_ctf(config._ctf)
        config.nan_color = [0.0, 0.0, 0.0, 0.0]
        config.cut_outside_range = True
        config._apply_nan_color()
        assert config._lut.GetAboveRangeColor() == pytest.approx((0.0, 0.0, 0.0, 0.0))
        assert config._lut.GetBelowRangeColor() == pytest.approx((0.0, 0.0, 0.0, 0.0))

    def test_lut_maps_nan_with_alpha_zero(self, config):
        from vtkmodules.vtkCommonCore import vtkDoubleArray

        config._build_lut_from_ctf(config._ctf)
        config.nan_color = [0.0, 0.0, 0.0, 0.0]
        config._apply_nan_color()
        arr = vtkDoubleArray()
        arr.InsertNextValue(float("nan"))
        colors = config._lut.MapScalars(arr, 0, 0)
        nc = colors.GetNumberOfComponents()
        alpha = colors.GetValue(nc - 1)
        assert alpha == 0, f"NaN alpha should be 0, got {alpha}"

    def test_lut_maps_valid_with_alpha_255(self, config):
        from vtkmodules.vtkCommonCore import vtkDoubleArray

        config._build_lut_from_ctf(config._ctf)
        vmin, vmax = config._ctf.GetRange()
        mid = (vmin + vmax) / 2.0
        arr = vtkDoubleArray()
        arr.InsertNextValue(mid)
        colors = config._lut.MapScalars(arr, 0, 0)
        nc = colors.GetNumberOfComponents()
        alpha = colors.GetValue(nc - 1)
        assert alpha == 255, f"Valid value alpha should be 255, got {alpha}"


class TestIndependentBands:
    def test_default_is_none(self, config):
        assert config.independent_bands == "none"

    def test_top(self, config):
        config._build_lut_from_ctf(config._ctf)
        config.independent_bands = "top"
        config._apply_nan_color()

        assert config._lut.GetUseAboveRangeColor() == 1
        assert config._lut.GetUseBelowRangeColor() == 0

    def test_bottom(self, config):
        config._build_lut_from_ctf(config._ctf)
        config.independent_bands = "bottom"
        config._apply_nan_color()

        assert config._lut.GetUseAboveRangeColor() == 0
        assert config._lut.GetUseBelowRangeColor() == 1

    def test_both(self, config):
        config._build_lut_from_ctf(config._ctf)
        config.independent_bands = "both"
        config._apply_nan_color()

        assert config._lut.GetUseAboveRangeColor() == 1
        assert config._lut.GetUseBelowRangeColor() == 1

    def test_band_colors(self, config):
        config._build_lut_from_ctf(config._ctf)

        config.independent_band_bottom_color = [0.3, 0.3, 0.3, 1.0]
        config.independent_band_top_color = [0.7, 0.7, 0.7, 1.0]
        config.independent_bands = "both"
        config._apply_nan_color()

        assert config._lut.GetBelowRangeColor() == pytest.approx((0.3, 0.3, 0.3, 1.0))
        assert config._lut.GetAboveRangeColor() == pytest.approx((0.7, 0.7, 0.7, 1.0))
