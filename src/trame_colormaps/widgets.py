from trame.app.dataclass import get_instance

from trame.widgets import html
from trame.widgets import vuetify3 as v3
from trame_colormaps import module

__all__ = [
    "ColorMapEditor",
    "HorizontalScalarBar",
    "VerticalScalarBar",
]


def buttons(name):
    return [
        {
            "icon": (
                f"{name}.color_blind ? 'mdi-shield-check-outline' : 'mdi-palette'"
            ),
            "click": f"{name}.color_blind = !{name}.color_blind",
            "tip": (
                f"'Toggle to ' + ({name}.color_blind ? "
                "'All Colors' : 'Colorblind Safe')"
            ),
        },
        {
            "icon": f"{name}.invert ? 'mdi-invert-colors' : 'mdi-invert-colors-off'",
            "click": f"{name}.invert = !{name}.invert",
            "tip": (
                f"'Toggle to ' + ({name}.invert ? 'Normal Preset' : 'Invert Preset')"
            ),
        },
        {
            "icon": (
                f"{name}.use_log_scale === 'log' ? 'mdi-math-log' : "
                f"{name}.use_log_scale === 'symlog' ? 'mdi-sine-wave' : 'mdi-stairs'"
            ),
            "click": (
                f"{name}.use_log_scale = {name}.diverging"
                f" ? ({name}.use_log_scale === 'linear' ? 'symlog' : 'linear')"
                f" : ({name}.use_log_scale === 'linear' ? 'log' : "
                f"{name}.use_log_scale === 'log' ? 'symlog' : 'linear')"
            ),
            "tip": (
                f"'Toggle to ' + ({name}.diverging"
                f" ? ({name}.use_log_scale === 'linear'"
                f" ? 'SymLog Scale' : 'Linear Scale')"
                f" : ({name}.use_log_scale === 'linear' ?"
                f" 'Log Scale' : {name}"
                ".use_log_scale === 'log' ? 'SymLog Scale' : 'Linear Scale'))"
            ),
        },
        {
            "icon": f"{name}.diverging ? 'mdi-triangle' : 'mdi-triangle-outline'",
            "click": f"{name}.diverging = !{name}.diverging",
            "tip": (
                f"'Toggle to ' + ({name}.diverging ? 'Normal Mode' : 'Difference Mode')"
            ),
        },
        {
            "icon": (
                f"{name}.override_range ? 'mdi-arrow-expand-horizontal' : 'mdi-pencil'"
            ),
            "click": (
                f"!{name}.diverging && ({name}.override_range = !{name}.override_range)"
            ),
            "tip": (
                f"{name}.diverging ? 'Range locked in Δ mode'"
                f" : 'Toggle to ' + ({name}.override_range ? "
                "'Data Range' : 'Custom Range')"
            ),
        },
        {
            "icon": (
                f"{name}.discrete_log ? 'mdi-view-sequential' :"
                " 'mdi-gradient-horizontal'"
            ),
            "click": f"{name}.discrete_log = !{name}.discrete_log",
            "tip": f"'Toggle to ' + ({name}.discrete_log ? 'Continuous' : 'Discrete')",
        },
    ]


def _fmt_expr(name, idx):
    """Return a JS expression that formats a color_range value compactly.

    - 0 → '0'
    - |v| >= 1000 or |v| < 0.01 → exponential with 1 decimal (e.g. '2.6e+2')
    - otherwise → up to 2 decimal places, trailing zeros stripped
    """
    val = f"{name}.color_range[{idx}]"
    return (
        f"(({val}) === 0 ? '0'"
        f" : (Math.abs({val}) >= 1000 || Math.abs({val}) < 0.01)"
        f"   ? ({val}).toExponential(1)"
        f"   : parseFloat(({val}).toFixed(2)))"
    )


class ColorMapEditor(v3.VCard):
    def __init__(self, name):
        super().__init__(classes="tcmap-editor")
        self.server.enable_module(module)

        with self:
            # --- Toolbar row: icon buttons + search + close ---
            with v3.VCardItem(classes="py-1 px-2"):
                with html.Div(classes="d-flex align-center ga-1"):
                    for b in buttons(name):
                        with html.Div():
                            v3.VBtn(
                                icon=(b["icon"],),
                                click=b["click"],
                                size="small",
                                variant="text",
                                classes="tcmap-editor-icon",
                            )
                            v3.VTooltip(
                                text=(b["tip"],),
                                activator="parent",
                                location="bottom",
                            )

                    v3.VSpacer()
                    v3.VTextField(
                        v_model=f"{name}.search",
                        clearable=True,
                        placeholder=(f"{name}.preset",),
                        click_clear=f"{name}.search = null",
                        single_line=True,
                        variant="solo",
                        density="compact",
                        flat=True,
                        hide_details="auto",
                        classes="tcmap-editor-search",
                        reverse=True,
                    )
                    v3.VBtn(
                        icon="mdi-close",
                        size="small",
                        variant="text",
                        classes="tcmap-editor-icon",
                        click=f"{name}.menu=false",
                    )

            # --- Discrete colors slider/input ---
            _discrete_label = (
                f"{name}.use_log_scale === 'linear'"
                " ? 'Colors per tick interval'"
                " : 'Colors per order of magnitude'"
            )
            with v3.VCardItem(v_show=f"{name}.discrete_log", classes="py-0 mb-2"):
                v3.VNumberInput(
                    v_model=f"{name}.n_discrete_colors",
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

            # --- Diverging mode inputs (abs_max + epsilon) ---
            with v3.VCardItem(v_show=f"{name}.diverging", classes="py-0 mb-2"):
                v3.VTextField(
                    v_model=f"{name}.abs_max",
                    label="|max|",
                    error=(f"!{name}.abs_max_valid",),
                    density="compact",
                    variant="outlined",
                    flat=True,
                    hide_details=True,
                    classes="mt-2",
                )
                v3.VTextField(
                    v_model=f"{name}.epsilon",
                    label="ε tolerance",
                    error=(f"!{name}.epsilon_valid",),
                    density="compact",
                    variant="outlined",
                    flat=True,
                    hide_details=True,
                    classes="mt-2",
                )

            # --- Custom range inputs (hidden when diverging) ---
            with v3.VCardItem(
                v_show=f"{name}.override_range && !{name}.diverging",
                classes="py-0 mb-2",
            ):
                v3.VTextField(
                    v_model=f"{name}.color_value_min",
                    label="Min",
                    error=(f"!{name}.color_value_min_valid",),
                    density="compact",
                    variant="outlined",
                    flat=True,
                    hide_details=True,
                    classes="mt-2",
                )
                v3.VTextField(
                    v_model=f"{name}.color_value_max",
                    label="Max",
                    error=(f"!{name}.color_value_max_valid",),
                    density="compact",
                    variant="outlined",
                    flat=True,
                    hide_details=True,
                    classes="mt-2",
                )

            # --- Preset list ---
            _click_args = (
                "["
                f"{name}._id,"
                "entry.name,"
                f"{name}.invert,"
                f"{name}.use_log_scale,"
                f"{name}.discrete_log,"
                f"{name}.n_discrete_colors,"
                f"{name}.n_colors"
                "]"
            )
            _v_for = (
                f"entry in ({name}.invert ? {name}.luts_inverted : {name}.luts_normal)"
            )
            _v_show = (
                f"({name}.search && {name}.search.length"
                f" ? entry.name.toLowerCase().includes({name}.search.toLowerCase())"
                " : 1)"
                f" && (!{name}.color_blind || entry.safe)"
            )
            v3.VDivider()
            with v3.VList(density="compact", max_height="40vh"):
                with v3.VListItem(
                    v_for=_v_for,
                    v_show=_v_show,
                    key="entry.name",
                    subtitle=("entry.name",),
                    click=(self.update_color_preset, _click_args),
                    active=(f"{name}.preset === entry.name",),
                ):
                    html.Img(
                        src=("entry.url",),
                        classes="rounded tcmap-img-preset",
                    )

    def update_color_preset(self, colormap_id, *args):
        color_map = get_instance(colormap_id)
        if color_map:
            color_map.update_color_preset(*args)


class HorizontalScalarBar(html.Div):
    def __init__(self, name, popup_location="top", **kwargs):
        super().__init__(
            classes="tcmap-horizontal bg-blue-grey-darken-2 d-flex align-center",
        )
        self.server.enable_module(module)

        with self:
            with v3.VMenu(
                v_model=f"{name}.menu",
                activator="parent",
                location=popup_location,
                close_on_content_click=False,
            ):
                ColorMapEditor(name)

            html.Div(
                f"{{{{ {name}.color_range && {name}.color_range[0] != null "
                f"? '' + {_fmt_expr(name, 0)} : '' }}}}",
                classes="text-caption px-2 text-no-wrap",
            )
            with html.Div(classes="tcmap-h-img-container rounded"):
                html.Img(
                    src=(f"{name}.lut_img_h",),
                    draggable=False,
                )
                with html.Div(classes="tcmap-ticks-container"):
                    with html.Div(
                        v_for=f"(tick, i) in {name}.color_ticks",
                        key="i",
                        classes="tcmap-tick-container",
                        style=(
                            "`top:0;left:${tick.position}%;flex-direction:column;transform:translateX(-50%);`",
                        ),
                    ):
                        html.Div(
                            classes="tcmap-tick-line-h",
                            style=("`background:${tick.color};`",),
                        )
                        html.Span(
                            "{{ tick.label }}",
                            classes="tcmap-tick-label",
                            style=("`color:${tick.color};`",),
                        )
            html.Div(
                f"{{{{ {name}.color_range && {name}.color_range[1] != null"
                f" ? {_fmt_expr(name, 1)} : '' }}}}",
                classes="text-caption px-2 text-no-wrap",
            )


class VerticalScalarBar(html.Div):
    def __init__(self, name, popup_location="top", **kwargs):
        super().__init__(
            classes=(
                "tcmap-vertical bg-blue-grey-darken-2 d-flex flex-column align-center"
            ),
        )
        self.server.enable_module(module)

        with self:
            with v3.VMenu(
                v_model=f"{name}.menu",
                activator="parent",
                location=popup_location,
                close_on_content_click=False,
            ):
                ColorMapEditor(name)

            # Max label at top
            html.Div(
                f"{{{{ {name}.color_range && {name}.color_range[1] != null"
                f" ? {_fmt_expr(name, 1)} : '' }}}}",
                classes="tcmap-vertical-labels text-caption text-no-wrap",
            )
            # Vertical LUT image stretched to fill
            with html.Div(classes="tcmap-v-img-container"):
                html.Img(
                    src=(f"{name}.lut_img_v",),
                    draggable=False,
                )
                # Tick overlay
                with html.Div(classes="tcmap-ticks-container"):
                    with html.Div(
                        v_for=f"(tick, i) in {name}.color_ticks",
                        key="i",
                        classes="tcmap-tick-container",
                        style=(
                            "`top:${100 - tick.position}%;left:0;"
                            "flex-direction:row;transform:translateY(-50%);`",
                        ),
                    ):
                        html.Div(
                            classes="tcmap-tick-line-v",
                            style=("`background:${tick.color};`",),
                        )
                        html.Span(
                            "{{ tick.label }}",
                            classes="tcmap-tick-label",
                            style=(
                                "`color: ${tick.color};"
                                "writing-mode:vertical-lr;"
                                "transform: rotate(180deg);`",
                            ),
                        )
            # Min label at bottom
            html.Div(
                f"{{{{ {name}.color_range && {name}.color_range[0] != null"
                f" ? {_fmt_expr(name, 0)} : '' }}}}",
                classes="tcmap-vertical-labels text-caption text-no-wrap",
            )
