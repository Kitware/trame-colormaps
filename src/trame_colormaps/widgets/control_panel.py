"""Colormap control panel widget.

Renders the settings popup for a colormap inside a VCard:
- Toggle buttons: color-blind filter, invert, scale mode (linear/log/symlog),
  custom range, discrete/continuous
- Discrete colors count input (shown when discrete mode is active)
- Manual min/max range inputs (shown when custom range is active)
- Searchable preset list with thumbnail images

Template bindings reference ``config.*`` via ``provide_as("config")``.
"""

from trame.widgets import html
from trame.widgets import vuetify3 as v3

_BTNS = [
    {
        "icon": "config.color_blind ? 'mdi-shield-check-outline' : 'mdi-palette'",
        "click": "config.color_blind = !config.color_blind",
        "tip": "'Toggle to ' + (config.color_blind ? 'All Colors' : 'Colorblind Safe')",
    },
    {
        "icon": "config.invert ? 'mdi-invert-colors' : 'mdi-invert-colors-off'",
        "click": "config.invert = !config.invert",
        "tip": "'Toggle to ' + (config.invert ? 'Normal Preset' : 'Invert Preset')",
    },
    {
        "icon": "config.use_log_scale === 'log' ? 'mdi-math-log' : config.use_log_scale === 'symlog' ? 'mdi-sine-wave' : 'mdi-stairs'",
        "click": "config.use_log_scale = config.use_log_scale === 'linear' ? 'log' : config.use_log_scale === 'log' ? 'symlog' : 'linear'",
        "tip": "'Toggle to ' + (config.use_log_scale === 'linear' ? 'Log Scale' : config.use_log_scale === 'log' ? 'SymLog Scale' : 'Linear Scale')",
    },
    {
        "icon": "config.override_range ? 'mdi-arrow-expand-horizontal' : 'mdi-pencil'",
        "click": "config.override_range = !config.override_range",
        "tip": "'Toggle to ' + (config.override_range ? 'Data Range' : 'Custom Range')",
    },
    {
        "icon": "config.discrete_log ? 'mdi-view-sequential' : 'mdi-gradient-horizontal'",
        "click": "config.discrete_log = !config.discrete_log",
        "tip": "'Toggle to ' + (config.discrete_log ? 'Continuous' : 'Discrete')",
    },
]

_ICON_STYLE = "min-width:0;width:24px;height:24px;padding:0;"


def _icon_btn(b):
    """Render an icon button with tooltip."""
    with html.Div(style="display:inline-flex;"):
        v3.VBtn(
            icon=(b["icon"],),
            click=b["click"],
            size="small",
            variant="text",
            style=_ICON_STYLE,
        )
        v3.VTooltip(
            text=(b["tip"],),
            activator="parent",
            location="bottom",
        )


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

    def render(self):
        """Emit the control panel DOM."""
        _render_control_panel(self._config, self._update_color_preset)


def create_control_panel(config, update_color_preset):
    """Create the colormap control panel menu content.

    Args:
        config: ColormapConfig (or compatible StateDataModel).
        update_color_preset: Callback for preset changes.
    """
    _render_control_panel(config, update_color_preset)


def _render_control_panel(config, update_color_preset):
    """Internal: emit the control panel DOM."""
    with v3.VCard(style="max-width: 360px;min-width: 360px;"):
        # --- Toolbar row: icon buttons + search + close ---
        with v3.VCardItem(classes="py-1 px-2"):
            with html.Div(classes="d-flex align-center", style="gap:2px;"):
                for _b in _BTNS:
                    _icon_btn(_b)
                v3.VSpacer()
                v3.VTextField(
                    v_model="config.search",
                    clearable=True,
                    placeholder=("config.preset",),
                    click_clear="config.search = null",
                    single_line=True,
                    variant="solo",
                    density="compact",
                    flat=True,
                    hide_details="auto",
                    style="max-width:120px;",
                    reverse=True,
                )
                v3.VBtn(
                    icon="mdi-close",
                    size="small",
                    variant="text",
                    style=_ICON_STYLE,
                    click="config.menu=false",
                )

        # --- Discrete colors slider/input ---
        _discrete_label = (
            "config.use_log_scale === 'linear'"
            " ? 'Colors per tick interval'"
            " : 'Colors per order of magnitude'"
        )
        with v3.VCardItem(v_show="config.discrete_log", classes="py-0 mb-2"):
            v3.VNumberInput(
                v_model="config.n_discrete_colors",
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

        # --- Custom range inputs ---
        _tf_kwargs_min = dict(
            v_model="config.color_value_min",
            hide_details=True,
            label="Min",
            classes="mt-2",
            error=("!config.color_value_min_valid",),
        )
        _tf_kwargs_max = dict(
            v_model="config.color_value_max",
            hide_details=True,
            label="Max",
            classes="mt-2",
            error=("!config.color_value_max_valid",),
        )
        with v3.VCardItem(v_show="config.override_range", classes="py-0 mb-2"):
            v3.VTextField(density="compact", variant="outlined", flat=True, **_tf_kwargs_min)
            v3.VTextField(density="compact", variant="outlined", flat=True, **_tf_kwargs_max)

        # --- Preset list ---
        _click_args = "[entry.name, config.invert, config.use_log_scale, config.discrete_log, config.n_discrete_colors, config.n_colors]"
        _v_for = "entry in (config.invert ? config.luts_inverted : config.luts_normal)"
        _v_show = (
            "(config.search && config.search.length"
            " ? entry.name.toLowerCase().includes(config.search.toLowerCase()) : 1)"
            " && (!config.color_blind || entry.safe)"
        )
        v3.VDivider()
        with v3.VList(density="compact", max_height="40vh"):
            with v3.VListItem(
                v_for=_v_for,
                v_show=_v_show,
                key="entry.name",
                subtitle=("entry.name",),
                click=(update_color_preset, _click_args),
                active=("config.preset === entry.name",),
            ):
                html.Img(
                    src=("entry.url",),
                    style="width:100%;min-width:20rem;height:1rem;",
                    classes="rounded",
                )
