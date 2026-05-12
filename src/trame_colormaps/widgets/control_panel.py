"""Colormap control panel widget.

Renders the settings popup for a colormap inside a VCard:
- Toggle buttons: color-blind filter, invert, scale mode (linear/log/symlog),
  custom range, discrete/continuous
- Discrete colors count input (shown when discrete mode is active)
- Manual min/max range inputs (shown when custom range is active)
- Searchable preset list with thumbnail images

Supports both Vuetify 2 and Vuetify 3 — detected automatically.

Template bindings use a *prefix* ``p`` so that the same logic works for
Vue 3 (``"config."`` → ``config.preset``) and Vue 2 (``"config_"`` →
``config_preset``).
"""

from trame.widgets import html

from trame_colormaps.widgets._compat import vuetify, is_v3


def _btns(p):
    """Return button definitions with the given variable prefix."""
    return [
        {
            "icon": f"{p}color_blind ? 'mdi-shield-check-outline' : 'mdi-palette'",
            "click": f"{p}color_blind = !{p}color_blind",
            "tip": f"'Toggle to ' + ({p}color_blind ? 'All Colors' : 'Colorblind Safe')",
        },
        {
            "icon": f"{p}invert ? 'mdi-invert-colors' : 'mdi-invert-colors-off'",
            "click": f"{p}invert = !{p}invert",
            "tip": f"'Toggle to ' + ({p}invert ? 'Normal Preset' : 'Invert Preset')",
        },
        {
            "icon": f"{p}use_log_scale === 'log' ? 'mdi-math-log' : {p}use_log_scale === 'symlog' ? 'mdi-sine-wave' : 'mdi-stairs'",
            "click": f"{p}use_log_scale = {p}use_log_scale === 'linear' ? 'log' : {p}use_log_scale === 'log' ? 'symlog' : 'linear'",
            "tip": f"'Toggle to ' + ({p}use_log_scale === 'linear' ? 'Log Scale' : {p}use_log_scale === 'log' ? 'SymLog Scale' : 'Linear Scale')",
        },
        {
            "icon": f"{p}override_range ? 'mdi-arrow-expand-horizontal' : 'mdi-pencil'",
            "click": f"{p}override_range = !{p}override_range",
            "tip": f"'Toggle to ' + ({p}override_range ? 'Data Range' : 'Custom Range')",
        },
        {
            "icon": f"{p}discrete_log ? 'mdi-view-sequential' : 'mdi-gradient-horizontal'",
            "click": f"{p}discrete_log = !{p}discrete_log",
            "tip": f"'Toggle to ' + ({p}discrete_log ? 'Continuous' : 'Discrete')",
        },
    ]


def _icon_btn_v3(v, b, style):
    """Render an icon button with tooltip — Vuetify 3."""
    with html.Div(style="display:inline-flex;"):
        v.VBtn(
            icon=(b["icon"],),
            click=b["click"],
            size="small",
            variant="text",
            style=style,
        )
        v.VTooltip(
            text=(b["tip"],),
            activator="parent",
            location="bottom",
        )


def _icon_btn_v2(v, b, style):
    """Render an icon button with tooltip — Vuetify 2."""
    with html.Div(style="display:inline-flex;"):
        with v.VTooltip(bottom=True):
            with html.Template(v_slot_activator="{ on, attrs }"):
                with v.VBtn(
                    icon=True,
                    v_on="on",
                    v_bind="attrs",
                    click=b["click"],
                    style=style,
                ):
                    v.VIcon("{{ %s }}" % b["icon"], small=True)
            html.Span("{{ %s }}" % b["tip"])


class ControlPanel:
    """Self-contained control panel for a colorbar.

    Owns no state of its own — renders UI bound to the given config
    and fires ``update_color_preset`` on preset selection.

    Args:
        config: ColormapConfig (or compatible StateDataModel).
        update_color_preset: Callback for preset changes.
    """

    def __init__(self, config, update_color_preset):
        self._config = config
        self._update_color_preset = update_color_preset

    def render(self, p="config."):
        """Emit the control panel DOM.

        Args:
            p: Variable prefix for template bindings.
                ``"config."`` for Vue 3, ``"config_"`` for Vue 2.
        """
        _render_control_panel(self._config, self._update_color_preset, p)


def create_control_panel(config, update_color_preset, p="config."):
    """Create the colormap control panel menu content.

    Args:
        config: ColormapConfig (or compatible StateDataModel).
        update_color_preset: Callback for preset changes.
        p: Variable prefix for template bindings.
            ``"config."`` for Vue 3, ``"config_"`` for Vue 2.
    """
    _render_control_panel(config, update_color_preset, p)


def _render_control_panel(config, update_color_preset, p="config."):
    """Internal: emit the control panel DOM."""
    v = vuetify()
    v3_mode = is_v3()
    _make_btn = _icon_btn_v3 if v3_mode else _icon_btn_v2
    _icon_style = "min-width:0;width:24px;height:24px;padding:0;"

    with v.VCard(style="max-width: 360px;min-width: 360px;"):
        # --- Toolbar row: icon buttons + search + close ---
        if v3_mode:
            _toolbar_ctx = v.VCardItem(classes="py-1 px-2")
        else:
            _toolbar_ctx = html.Div(classes="pa-1")

        with _toolbar_ctx:
            _gap = "gap:2px;" if v3_mode else "gap:0;"
            with html.Div(classes="d-flex align-center", style=_gap):
                for _b in _btns(p):
                    _make_btn(v, _b, _icon_style)
                v.VSpacer()
                if v3_mode:
                    v.VTextField(
                        v_model=f"{p}search",
                        clearable=True,
                        placeholder=(f"{p}preset",),
                        click_clear=f"{p}search = null",
                        single_line=True,
                        variant="solo",
                        density="compact",
                        flat=True,
                        hide_details="auto",
                        style="max-width:120px;",
                        reverse=True,
                    )
                    v.VBtn(
                        icon="mdi-close",
                        size="small",
                        variant="text",
                        style=_icon_style,
                        click=f"{p}menu=false",
                    )
                else:
                    v.VTextField(
                        v_model=f"{p}search",
                        clearable=True,
                        placeholder=(f"{p}preset",),
                        click_clear=f"{p}search = null",
                        single_line=True,
                        solo=True,
                        dense=True,
                        flat=True,
                        hide_details="auto",
                        style="max-width:120px;",
                        reverse=True,
                    )
                    with v.VBtn(
                        icon=True,
                        small=True,
                        click=f"{p}menu=false",
                    ):
                        v.VIcon("mdi-close", small=True)

        # --- Discrete colors slider/input ---
        _discrete_label = (
            f"{p}use_log_scale === 'linear'"
            " ? 'Colors per tick interval'"
            " : 'Colors per order of magnitude'"
        )
        if v3_mode:
            with v.VCardItem(v_show=f"{p}discrete_log", classes="py-0 mb-2"):
                v.VNumberInput(
                    v_model=f"{p}n_discrete_colors",
                    hide_details=True,
                    density="compact",
                    variant="outlined",
                    flat=True,
                    label=(_discrete_label,),
                    classes="mt-2",
                    step=[1],
                    min=[1],
                    max=[20],
                )
        else:
            with html.Div(v_show=f"{p}discrete_log", classes="px-4 pb-2"):
                v.VTextField(
                    v_model_number=f"{p}n_discrete_colors",
                    hide_details=True,
                    dense=True,
                    outlined=True,
                    label=(_discrete_label,),
                    type="number",
                    min=1,
                    max=20,
                    step=1,
                    __properties=[("v_model_number", "v-model.number")],
                )

        # --- Custom range inputs ---
        if v3_mode:
            _range_ctx = v.VCardItem(
                v_show=f"{p}override_range", classes="py-0 mb-2"
            )
        else:
            _range_ctx = html.Div(
                v_show=f"{p}override_range", classes="px-4 pb-2"
            )
        _tf_kwargs_min = dict(
            v_model=f"{p}color_value_min",
            hide_details=True,
            label="Min",
            classes="mt-2",
            error=(f"!{p}color_value_min_valid",),
        )
        _tf_kwargs_max = dict(
            v_model=f"{p}color_value_max",
            hide_details=True,
            label="Max",
            classes="mt-2",
            error=(f"!{p}color_value_max_valid",),
        )
        with _range_ctx:
            if v3_mode:
                v.VTextField(density="compact", variant="outlined", flat=True, **_tf_kwargs_min)
                v.VTextField(density="compact", variant="outlined", flat=True, **_tf_kwargs_max)
            else:
                v.VTextField(dense=True, outlined=True, **_tf_kwargs_min)
                v.VTextField(dense=True, outlined=True, **_tf_kwargs_max)

        # --- Preset list ---
        _click_args = f"[entry.name, {p}invert, {p}use_log_scale, {p}discrete_log, {p}n_discrete_colors, {p}n_colors]"
        _v_for = f"entry in ({p}invert ? {p}luts_inverted : {p}luts_normal)"
        _v_show = (
            f"({p}search && {p}search.length"
            f" ? entry.name.toLowerCase().includes({p}search.toLowerCase()) : 1)"
            f" && (!{p}color_blind || entry.safe)"
        )
        v.VDivider()
        if v3_mode:
            with v.VList(density="compact", max_height="40vh"):
                with v.VListItem(
                    v_for=_v_for,
                    v_show=_v_show,
                    key="entry.name",
                    subtitle=("entry.name",),
                    click=(update_color_preset, _click_args),
                    active=(f"{p}preset === entry.name",),
                ):
                    html.Img(
                        src=("entry.url",),
                        style="width:100%;min-width:20rem;height:1rem;",
                        classes="rounded",
                    )
        else:
            with v.VList(dense=True, style="max-height:40vh;overflow-y:auto;"):
                with v.VListItem(
                    v_for=_v_for,
                    v_show=_v_show,
                    key="entry.name",
                    click=(update_color_preset, _click_args),
                    active=(f"{p}preset === entry.name",),
                ):
                    with v.VListItemContent():
                        v.VListItemSubtitle("{{ entry.name }}")
                        html.Img(
                            src=("entry.url",),
                            style="width:100%;min-width:20rem;height:1rem;",
                            classes="rounded",
                        )
