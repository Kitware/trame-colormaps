"""Tests for trame_colormaps.widgets — buttons helper and widget exports."""

from trame_colormaps.widgets import (
    ColorMapEditor,
    HorizontalScalarBar,
    VerticalScalarBar,
    buttons,
)

# --- buttons() ---


class TestButtons:
    def test_returns_list(self):
        result = buttons("cfg")
        assert isinstance(result, list)

    def test_seven_buttons(self):
        result = buttons("cfg")
        assert len(result) == 7

    def test_each_has_icon_click_tip(self):
        for btn in buttons("cfg"):
            assert "icon" in btn
            assert "click" in btn
            assert "tip" in btn

    def test_name_interpolation(self):
        """All click/tip strings should contain the given name."""
        for btn in buttons("myConfig"):
            assert "myConfig" in btn["click"]
            assert "myConfig" in btn["tip"]

    def test_color_blind_button(self):
        btn = buttons("c")[1]
        assert "color_blind" in btn["click"]

    def test_invert_button(self):
        btn = buttons("c")[2]
        assert "invert" in btn["click"]

    def test_log_scale_button(self):
        btn = buttons("c")[3]
        assert "use_log_scale" in btn["click"]
        assert "log" in btn["click"] or "symlog" in btn["click"]

    def test_diverging_button(self):
        btn = buttons("c")[4]
        assert "diverging" in btn["click"]
        assert "Difference" in btn["tip"]

    def test_override_range_button(self):
        btn = buttons("c")[5]
        assert "override_range" in btn["click"]

    def test_discrete_button(self):
        btn = buttons("c")[6]
        assert "discrete_log" in btn["click"]

    def test_palette_button(self):
        btn = buttons("c")[0]
        assert "show_categories" in btn["click"]
        assert "palette" in btn["icon"]

    def test_log_icon_f_string(self):
        """Regression: symlog icon expression must interpolate the name."""
        btn = buttons("cfg")[3]
        # The icon string should NOT contain literal '{name}'
        assert "{name}" not in btn["icon"]
        assert "cfg" in btn["icon"]


# --- Widget classes exist ---


class TestWidgetExports:
    def test_color_map_editor_is_class(self):
        assert isinstance(ColorMapEditor, type)

    def test_horizontal_scalar_bar_is_class(self):
        assert isinstance(HorizontalScalarBar, type)

    def test_vertical_scalar_bar_is_class(self):
        assert isinstance(VerticalScalarBar, type)
