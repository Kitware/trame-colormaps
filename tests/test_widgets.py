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

    def test_nine_entries(self):
        result = buttons("cfg")
        assert len(result) == 9

    def test_each_has_icon_click_tip(self):
        for btn in buttons("cfg"):
            if btn.get("separator"):
                continue
            assert "icon" in btn
            assert "click" in btn
            assert "tip" in btn

    def test_name_interpolation(self):
        """All click/tip strings should contain the given name."""
        for btn in buttons("myConfig"):
            if btn.get("separator"):
                continue
            assert "myConfig" in btn["click"]
            assert "myConfig" in btn["tip"]

    def test_color_blind_button(self):
        btn = buttons("c")[4]
        assert "color_blind" in btn["click"]

    def test_invert_button(self):
        btn = buttons("c")[5]
        assert "invert" in btn["click"]

    def test_log_scale_button(self):
        btn = buttons("c")[0]
        assert "use_log_scale" in btn["click"]
        assert "log" in btn["click"] or "symlog" in btn["click"]

    def test_diverging_button(self):
        btn = buttons("c")[1]
        assert "diverging" in btn["click"]
        assert "Difference" in btn["tip"]

    def test_override_range_button(self):
        btn = buttons("c")[8]
        assert "override_range" in btn["click"]

    def test_discrete_button(self):
        btn = buttons("c")[7]
        assert "discrete_log" in btn["click"]

    def test_palette_button(self):
        btn = buttons("c")[3]
        assert "show_categories" in btn["click"]
        assert "palette" in btn["icon"]  # static icon, outline from variant

    def test_log_icon_f_string(self):
        """Regression: symlog icon expression must interpolate the name."""
        btn = buttons("cfg")[0]
        # The icon string should NOT contain literal '{name}'
        assert "{name}" not in btn["icon"]
        assert "cfg" in btn["icon"]

    def test_separators_at_correct_positions(self):
        result = buttons("c")
        assert result[2].get("separator") is True
        assert result[6].get("separator") is True

    def test_all_buttons_have_active_field(self):
        for btn in buttons("c"):
            if btn.get("separator"):
                continue
            assert "active" in btn

    def test_scale_button_always_active(self):
        btn = buttons("c")[0]
        assert btn["active"] == "true"

    def test_diverging_disabled_when_log_or_override(self):
        btn = buttons("c")[1]
        assert "disabled" in btn
        assert "use_log_scale === 'log'" in btn["disabled"]
        assert "override_range" in btn["disabled"]

    def test_diverging_can_toggle_off_when_active(self):
        """Click expression allows toggling off even when disabled conditions met."""
        btn = buttons("c")[1]
        # The click guard allows toggling when already diverging
        assert "c.diverging ||" in btn["click"] or "(c.diverging ||" in btn["click"]

    def test_override_range_disabled_when_diverging(self):
        btn = buttons("c")[8]
        assert "disabled" in btn
        assert "diverging" in btn["disabled"]

    def test_palette_button_is_menu(self):
        btn = buttons("c")[3]
        assert btn.get("menu") is True

    def test_palette_never_active(self):
        btn = buttons("c")[3]
        assert btn["active"] == "false"

    def test_palette_disabled_when_diverging(self):
        btn = buttons("c")[3]
        assert "disabled" in btn
        assert "diverging" in btn["disabled"]

    def test_non_scale_icons_are_static(self):
        """All buttons except scale have static icon strings (no ternary)."""
        for i, btn in enumerate(buttons("c")):
            if btn.get("separator") or i == 0:
                continue
            # Static icons are quoted literals like "'mdi-xxx'"
            assert btn["icon"].startswith("'"), f"Button {i} icon is not static"


# --- Widget classes exist ---


class TestWidgetExports:
    def test_color_map_editor_is_class(self):
        assert isinstance(ColorMapEditor, type)

    def test_horizontal_scalar_bar_is_class(self):
        assert isinstance(HorizontalScalarBar, type)

    def test_vertical_scalar_bar_is_class(self):
        assert isinstance(VerticalScalarBar, type)
