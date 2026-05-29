"""Tests for trame_colormaps.widgets — buttons helper and widget exports."""

from trame_colormaps.widgets import (
    NAN_COLOR_OPTIONS,
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

    def test_eleven_entries(self):
        result = buttons("cfg")
        assert len(result) == 11

    def test_each_has_icon_click_tip(self):
        for btn in buttons("cfg"):
            if btn.get("separator"):
                continue
            assert "icon" in btn
            # nan_menu and category menu don't have click
            if not btn.get("nan_menu") and not btn.get("menu"):
                assert "click" in btn
            assert "tip" in btn

    def test_name_interpolation(self):
        """All click/tip strings should contain the given name."""
        for btn in buttons("myConfig"):
            if btn.get("separator") or btn.get("nan_menu"):
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
        btn = buttons("c")[9]
        assert "override_range" in btn["click"]

    def test_discrete_button(self):
        btn = buttons("c")[8]
        assert "discrete_log" in btn["click"]

    def test_palette_button(self):
        btn = buttons("c")[3]
        assert "show_categories" in btn["click"]
        assert btn["icon"] == "mdi-palette"

    def test_log_icon_f_string(self):
        """Regression: symlog icon expression must interpolate the name."""
        btn = buttons("cfg")[0]
        icon = btn["icon"][0] if isinstance(btn["icon"], tuple) else btn["icon"]
        assert "{name}" not in icon
        assert "cfg" in icon

    def test_separators_at_correct_positions(self):
        result = buttons("c")
        assert result[2].get("separator") is True
        assert result[7].get("separator") is True

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
        btn = buttons("c")[9]
        assert "disabled" in btn
        assert "diverging" in btn["disabled"]

    def test_nan_menu_button(self):
        btn = buttons("c")[6]
        assert btn.get("nan_menu") is True
        assert btn["icon"] == "mdi-crosshairs-question"
        assert btn["active"] == "false"

    def test_cut_outside_range_button(self):
        btn = buttons("c")[10]
        assert btn["icon"] == "mdi-scissors-cutting"
        assert "cut_outside_range" in btn["click"]
        assert "cut_outside_range" in btn["active"]

    def test_cut_disabled_without_override_or_diverging(self):
        btn = buttons("c")[10]
        assert "disabled" in btn
        assert "override_range" in btn["disabled"]
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
        """All buttons except scale have plain mdi- icon strings."""
        for i, btn in enumerate(buttons("c")):
            if btn.get("separator") or i == 0:
                continue
            assert btn["icon"].startswith("mdi-"), f"Button {i} icon is not static"

    def test_scale_icon_is_reactive_tuple(self):
        btn = buttons("c")[0]
        assert isinstance(btn["icon"], tuple)


# --- Widget classes exist ---


class TestWidgetExports:
    def test_color_map_editor_is_class(self):
        assert isinstance(ColorMapEditor, type)

    def test_horizontal_scalar_bar_is_class(self):
        assert isinstance(HorizontalScalarBar, type)

    def test_vertical_scalar_bar_is_class(self):
        assert isinstance(VerticalScalarBar, type)


# --- NAN_COLOR_OPTIONS ---


class TestNanColorOptions:
    def test_is_list(self):
        assert isinstance(NAN_COLOR_OPTIONS, list)

    def test_has_19_entries(self):
        assert len(NAN_COLOR_OPTIONS) == 19

    def test_first_is_transparent(self):
        first = NAN_COLOR_OPTIONS[0]
        assert first["situation_preset_type"] == "transparent"
        assert first["color"] == [0.0, 0.0, 0.0, 0.0]

    def test_each_has_color_and_label(self):
        for opt in NAN_COLOR_OPTIONS:
            assert "color" in opt
            assert "situation_preset_type" in opt
            assert len(opt["color"]) == 4

    def test_no_duplicate_colors(self):
        colors = [tuple(o["color"]) for o in NAN_COLOR_OPTIONS]
        assert len(colors) == len(set(colors))

    def test_no_duplicate_labels(self):
        labels = [o["situation_preset_type"] for o in NAN_COLOR_OPTIONS]
        assert len(labels) == len(set(labels))

    def test_all_rgba_values_in_range(self):
        for opt in NAN_COLOR_OPTIONS:
            for v in opt["color"]:
                assert 0.0 <= v <= 1.0
