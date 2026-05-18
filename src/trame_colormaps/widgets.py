from trame.app.dataclass import get_instance

from trame.widgets import html
from trame.widgets import vuetify3 as v3

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
                f"{name}.use_log_scale = {name}.use_log_scale === 'linear' ? 'log' : "
                f"{name}.use_log_scale === 'log' ? 'symlog' : 'linear'"
            ),
            "tip": (
                f"'Toggle to ' + ({name}.use_log_scale === 'linear' ?"
                f" 'Log Scale' : {name}"
                ".use_log_scale === 'log' ? 'SymLog Scale' : 'Linear Scale')"
            ),
        },
        {
            "icon": (
                f"{name}.override_range ? 'mdi-arrow-expand-horizontal' : 'mdi-pencil'"
            ),
            "click": f"{name}.override_range = !{name}.override_range",
            "tip": (
                f"'Toggle to ' + ({name}.override_range ? "
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


_ICON_STYLE = "min-width:0;width:24px;height:24px;padding:0;"


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
        super().__init__(style="max-width: 360px;min-width: 360px;")

        with self:
            # --- Toolbar row: icon buttons + search + close ---
            with v3.VCardItem(classes="py-1 px-2"):
                with html.Div(classes="d-flex align-center", style="gap:2px;"):
                    for b in buttons(name):
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
                        style="max-width:120px;",
                        reverse=True,
                    )
                    v3.VBtn(
                        icon="mdi-close",
                        size="small",
                        variant="text",
                        style=_ICON_STYLE,
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

            # --- Custom range inputs ---
            with v3.VCardItem(v_show=f"{name}.override_range", classes="py-0 mb-2"):
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
                        style="width:100%;min-width:20rem;height:1rem;",
                        classes="rounded",
                    )

    def update_color_preset(self, colormap_id, *args):
        color_map = get_instance(colormap_id)
        if color_map:
            color_map.update_color_preset(*args)


class HorizontalScalarBar(html.Div):
    def __init__(self, name, popup_location="top", **kwargs):
        super().__init__(
            classes="bg-blue-grey-darken-2 d-flex align-center",
            style="width:100%;height:1rem;user-select:none;cursor:context-menu;",
        )

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
                f"? {_fmt_expr(name, 0)} : '' }}}}",
                classes="text-caption px-2 text-no-wrap",
            )
            with html.Div(
                classes="rounded w-100",
                style="height:70%;position:relative;",
            ):
                html.Img(
                    src=(f"{name}.lut_img_h",),
                    style="width:100%;height:2rem;",
                    draggable=False,
                )
                with html.Div(
                    style="position:absolute;top:0;left:0;right:0;bottom:0;pointer-events:none;",
                ):
                    with html.Div(
                        v_for=f"(tick, i) in {name}.color_ticks",
                        key="i",
                        style=(
                            "`position:absolute;left:${tick.position}%;"
                            "top:0;height:100%;transform:translateX(-50%);"
                            "display:flex;flex-direction:column;"
                            "align-items:center;`",
                        ),
                    ):
                        html.Div(
                            style=(
                                "`width:1.5px;height:30%;background:${tick.color};`",
                            ),
                        )
                        html.Span(
                            "{{ tick.label }}",
                            style=(
                                "`font-size:0.5rem;line-height:1;white-space:nowrap;color:${tick.color};`",
                            ),
                        )
                        html.Div(
                            style=("`width:1.5px;flex:1;background:${tick.color};`",),
                        )
            html.Div(
                f"{{{{ {name}.color_range && {name}.color_range[1] != null"
                f" ? {_fmt_expr(name, 1)} : '' }}}}",
                classes="text-caption px-2 text-no-wrap",
            )


class VerticalScalarBar(html.Div):
    def __init__(self, name, popup_location="top", **kwargs):
        super().__init__(
            classes="bg-blue-grey-darken-2 d-flex flex-column align-center",
            style="width:1rem;height:100%;user-select:none;cursor:context-menu;",
        )

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
                classes="text-caption text-no-wrap",
                style=(
                    "font-size: 0.5rem;"
                    "writing-mode: vertical-lr;"
                    "transform: rotate(180deg);"
                    "padding: 2px 0;"
                ),
            )
            # Vertical LUT image stretched to fill
            with html.Div(
                style="flex:1;width:100%;position:relative;min-height:0;",
            ):
                html.Img(
                    src=(f"{name}.lut_img_v",),
                    style="width:100%;height:100%;",
                    draggable=False,
                )
                # Tick overlay
                with html.Div(
                    style="position:absolute;top:0;left:0;right:0;bottom:0;pointer-events:none;",
                ):
                    with html.Div(
                        v_for=f"(tick, i) in {name}.color_ticks",
                        key="i",
                        style=(
                            "`position:absolute;"
                            "top:${100 - tick.position}%;"
                            "left:0;"
                            "width:100%;"
                            "transform:translateY(-50%);"
                            "display:flex;"
                            "flex-direction:row;"
                            "align-items:center;`",
                        ),
                    ):
                        html.Div(
                            style=(
                                "`width:100%;height:1.5px;background:${tick.color};`",
                            ),
                        )
                        html.Span(
                            "{{ tick.label }}",
                            style=(
                                "`font-size: 0.5rem;"
                                "line-height: 1;"
                                "white-space: nowrap;"
                                "color: ${tick.color};"
                                "writing-mode:vertical-lr;"
                                "transform: rotate(180deg);"
                                "padding-left:2px;`",
                            ),
                        )
            # Min label at bottom
            html.Div(
                f"{{{{ {name}.color_range && {name}.color_range[0] != null"
                f" ? {_fmt_expr(name, 0)} : '' }}}}",
                classes="text-caption text-no-wrap",
                style=(
                    "font-size:0.5rem;"
                    "writing-mode:vertical-lr;"
                    "transform:rotate(180deg);"
                    "padding:2px 0;"
                ),
            )
