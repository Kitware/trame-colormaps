from trame.app.dataclass import get_instance

from trame.widgets import html
from trame.widgets import vuetify3 as v3
from trame_colormaps import module

__all__ = [
    "ColorMapEditor",
    "HorizontalScalarBar",
    "VerticalScalarBar",
]

NAN_COLOR_OPTIONS = [
    # Default
    {"color": [0.0, 0.0, 0.0, 0.0], "situation_preset_type": "Transparent"},
    {"color": [0.75, 0.75, 0.75, 1.0], "situation_preset_type": "General"},
    # Colormap types
    {"color": [0.85, 0.85, 0.85, 1.0], "situation_preset_type": "Sequential maps"},
    {"color": [0.60, 0.60, 0.60, 1.0], "situation_preset_type": "Diverging maps"},
    {"color": [0.80, 0.80, 0.80, 1.0], "situation_preset_type": "Categorical maps"},
    {"color": [0.22, 0.49, 0.72, 1.0], "situation_preset_type": "Grayscale maps"},
    {"color": [0.0, 0.0, 0.0, 1.0], "situation_preset_type": "Bright maps"},
    {"color": [1.0, 1.0, 1.0, 1.0], "situation_preset_type": "Dark maps"},
    {"color": [0.0, 1.0, 1.0, 1.0], "situation_preset_type": "Hot maps"},
    {"color": [0.74, 0.74, 0.74, 1.0], "situation_preset_type": "Terrain maps"},
    # Data quality
    {"color": [0.89, 0.10, 0.11, 1.0], "situation_preset_type": "Error"},
    {"color": [1.0, 1.0, 0.20, 1.0], "situation_preset_type": "Warning"},
    {"color": [1.0, 0.50, 0.0, 1.0], "situation_preset_type": "Suspect data"},
    {"color": [0.30, 0.69, 0.29, 1.0], "situation_preset_type": "Masked data"},
    {"color": [1.0, 0.0, 1.0, 1.0], "situation_preset_type": "Debugging"},
    # Background/context
    {"color": [0.55, 0.55, 0.55, 1.0], "situation_preset_type": "Light background"},
    {"color": [0.33, 0.33, 0.33, 1.0], "situation_preset_type": "Dark background"},
    {"color": [0.94, 0.94, 0.94, 1.0], "situation_preset_type": "Publication light"},
    {"color": [0.15, 0.15, 0.15, 1.0], "situation_preset_type": "Publication dark"},
]


def buttons(name):
    return [
        {
            "icon": (
                f"{name}.use_log_scale === 'linear' ? 'mdi-stairs' : "
                f"{name}.use_log_scale === 'log' ? 'mdi-math-log' : "
                "'mdi-sine-wave'",
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
            "active": "true",
        },
        {
            "icon": "mdi-triangle-outline",
            "click": (
                f"({name}.diverging || ({name}.use_log_scale !== 'log'"
                f" && !{name}.override_range))"
                f" && ({name}.diverging = !{name}.diverging)"
            ),
            "tip": (
                f"!{name}.diverging && {name}.use_log_scale === 'log'"
                f" ? 'Δ mode unavailable in Log scale'"
                f" : !{name}.diverging && {name}.override_range"
                f" ? 'Δ mode unavailable with custom range'"
                f" : 'Toggle to ' + ({name}.diverging ? 'Normal Mode' : 'Difference Mode')"
            ),
            "active": f"{name}.diverging",
            "disabled": (
                f"!{name}.diverging && "
                f"({name}.use_log_scale === 'log' || {name}.override_range)"
            ),
        },
        {"separator": True},
        {
            "icon": "mdi-palette",
            "click": f"{name}.show_categories = !{name}.show_categories",
            "tip": (
                f"{name}.diverging"
                f" ? 'Presets locked to Diverging in Δ mode'"
                f" : 'Select preset category'"
            ),
            "active": "false",
            "disabled": f"{name}.diverging",
            "menu": True,
        },
        {
            "icon": "mdi-blinds",
            "click": f"{name}.color_blind = !{name}.color_blind",
            "tip": (f"'Toggle to ' + ({name}.color_blind ? 'All Colors' : 'Colorblind Safe')"),
            "active": f"{name}.color_blind",
        },
        {
            "icon": "mdi-invert-colors",
            "click": f"{name}.invert = !{name}.invert",
            "tip": (f"'Toggle to ' + ({name}.invert ? 'Normal Preset' : 'Invert Preset')"),
            "active": f"{name}.invert",
        },
        {
            "icon": "mdi-crosshairs-question",
            "tip": "'NaN Color'",
            "active": "false",
            "nan_menu": True,
        },
        {"separator": True},
        {
            "icon": "mdi-gradient-horizontal",
            "click": f"{name}.discrete_log = !{name}.discrete_log",
            "tip": f"'Toggle to ' + ({name}.discrete_log ? 'Continuous' : 'Discrete')",
            "active": f"{name}.discrete_log",
        },
        {
            "icon": "mdi-pencil",
            "click": (f"!{name}.diverging && ({name}.override_range = !{name}.override_range)"),
            "tip": (
                f"{name}.diverging ? 'Custom range unavailable in Δ mode'"
                f" : 'Toggle to ' + ({name}.override_range ? "
                "'Data Range' : 'Custom Range')"
            ),
            "active": f"!{name}.diverging && {name}.override_range",
            "disabled": f"{name}.diverging",
        },
        {
            "icon": "mdi-arrow-expand-vertical",
            "tip": "'Independent Bands'",
            "active": f"{name}.independent_bands !== 'none'",
            "disabled": f"!{name}.override_range && !{name}.diverging",
            "show": f"{name}.enable_independent_bands",
            "independent_bands_menu": True,
        },
        {
            "icon": "mdi-scissors-cutting",
            "click": (
                f"({name}.override_range || {name}.diverging)"
                f" && ({name}.cut_outside_range = !{name}.cut_outside_range)"
                f" && ({name}.independent_bands = 'none')"
            ),
            "tip": (
                f"!{name}.override_range && !{name}.diverging"
                f" ? 'Cut mode requires Custom Range or Δ mode'"
                f" : 'Toggle to ' + ({name}.cut_outside_range"
                f" ? 'Clamp (endpoint colors)' : 'Cut (NaN color)')"
            ),
            "active": f"{name}.cut_outside_range",
            "disabled": f"!{name}.override_range && !{name}.diverging",
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
    def __init__(self, name, show_close_button=True, **kwargs):
        super().__init__(**{"classes": "tcmap-editor d-flex flex-column", **kwargs})
        self.server.enable_module(module)

        with self:
            # --- Toolbar row: icon buttons + search + close ---
            with v3.VCardItem(classes="py-1 px-2"):
                with html.Div(classes="d-flex align-center", style="gap: 1px;"):
                    for b in buttons(name):
                        if b.get("separator"):
                            v3.VDivider(vertical=True, classes="mx-0 my-auto", length="20")
                            continue
                        btn_kwargs = dict(
                            icon=b["icon"],
                            size="small",
                            variant=(f"{b['active']} ? 'outlined' : 'text'",),
                            color=(f"{b['active']} ? 'primary' : undefined",),
                            classes="tcmap-editor-icon",
                        )
                        if "disabled" in b:
                            btn_kwargs["disabled"] = (b["disabled"],)
                        if b.get("menu"):
                            with html.Div():
                                with v3.VMenu(
                                    v_model=f"{name}.show_categories",
                                    close_on_content_click=False,
                                    location="bottom",
                                ):
                                    with html.Template(v_slot_activator="{ props: menuProps }"):
                                        btn_kwargs["v_bind"] = "menuProps"
                                        v3.VBtn(**btn_kwargs)
                                    with v3.VList(density="compact"):
                                        for cat_value, cat_label in [
                                            ("sequential", "Sequential"),
                                            ("multi-sequential", "Multi-Sequential"),
                                            ("diverging", "Diverging"),
                                            ("cyclic", "Cyclic"),
                                        ]:
                                            v3.VListItem(
                                                title=cat_label,
                                                value=cat_value,
                                                click=(
                                                    f"{name}.selected_categories"
                                                    f" = '{cat_value}';"
                                                    f" {name}.search = null;"
                                                    f" {name}.show_categories"
                                                    " = false"
                                                ),
                                                active=(
                                                    f"{name}.selected_categories"
                                                    f" === '{cat_value}'",
                                                ),
                                            )
                                v3.VTooltip(
                                    text=(b["tip"],),
                                    activator="parent",
                                    location="bottom",
                                )
                        elif b.get("independent_bands_menu"):
                            with html.Div(
                                v_if=b.get("show"),
                            ):
                                with v3.VMenu(
                                    v_model=f"{name}.show_independent_bands_menu",
                                    location="bottom",
                                ):
                                    with html.Template(v_slot_activator="{ props: bandProps }"):
                                        btn_kwargs["v_bind"] = "bandProps"
                                        btn_kwargs["variant"] = "'text'"
                                        btn_kwargs["color"] = "undefined"
                                        v3.VBtn(**btn_kwargs)

                                    with v3.VList(density="compact"):
                                        for value, label in [
                                            ("none", "None"),
                                            ("top", "Top"),
                                            ("bottom", "Bottom"),
                                            ("both", "Top and Bottom"),
                                        ]:
                                            cut_reset = (
                                                f" {name}.cut_outside_range = false;"
                                                if value != "none"
                                                else ""
                                            )

                                            v3.VListItem(
                                                title=label,
                                                value=value,
                                                active=(
                                                    f"{name}.independent_bands === '{value}'"
                                                ),
                                                click=(
                                                    f"{name}.independent_bands"
                                                    f" = '{value}';"
                                                    f"{cut_reset}"
                                                    f" {name}.show_independent_bands_menu"
                                                    " = false"
                                                ),
                                            )

                                v3.VTooltip(
                                    text=(b["tip"],),
                                    activator="parent",
                                    location="bottom",
                                )
                        elif b.get("nan_menu"):
                            with html.Div():
                                with v3.VMenu(
                                    v_model=f"{name}.show_nan_menu",
                                    close_on_content_click=False,
                                    location="bottom",
                                ):
                                    with html.Template(v_slot_activator="{ props: nanProps }"):
                                        btn_kwargs["v_bind"] = "nanProps"
                                        btn_kwargs["variant"] = "'text'"
                                        btn_kwargs["color"] = "undefined"
                                        v3.VBtn(**btn_kwargs)
                                    with v3.VList(density="compact", max_height="300"):
                                        for nc in NAN_COLOR_OPTIONS:
                                            rgba = nc["color"]
                                            label = nc["situation_preset_type"]
                                            r255 = int(rgba[0] * 255)
                                            g255 = int(rgba[1] * 255)
                                            b255 = int(rgba[2] * 255)
                                            a_val = rgba[3]
                                            color_json = (
                                                f"[{rgba[0]},{rgba[1]},{rgba[2]},{rgba[3]}]"
                                            )
                                            icon_color = f"rgb({r255},{g255},{b255})"
                                            item_classes = "tcmap-nan-swatch" + (
                                                " tcmap-nan-checkerboard" if a_val == 0 else ""
                                            )
                                            v3.VListItem(
                                                title=label,
                                                value=label,
                                                prepend_icon="mdi-circle",
                                                classes=item_classes,
                                                style=f"--nan-icon-color: {icon_color};",
                                                click=(
                                                    f"{name}.nan_color = {color_json};"
                                                    f" {name}.show_nan_menu = false"
                                                ),
                                            )
                                v3.VTooltip(
                                    text=(b["tip"],),
                                    activator="parent",
                                    location="bottom",
                                )
                        else:
                            btn_kwargs["click"] = b["click"]
                            with html.Div():
                                v3.VBtn(**btn_kwargs)
                                v3.VTooltip(
                                    text=(b["tip"],),
                                    activator="parent",
                                    location="bottom",
                                )

                    html.Div(style="width: 4px; flex-shrink: 0;")
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
                    if show_close_button:
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
                f"{name}.n_ticks"
                "]"
            )
            _v_for = f"entry in ({name}.invert ? {name}.luts_inverted : {name}.luts_normal)"
            _v_show = (
                f"({name}.search && {name}.search.length"
                f" ? entry.name.toLowerCase().includes({name}.search.toLowerCase())"
                " : 1)"
                f" && (!{name}.color_blind || entry.safe)"
            )
            v3.VDivider()
            with html.Div(classes="flex-fill", style="overflow:auto;"):
                with v3.VList(density="compact"):
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
    def __init__(
        self, name, popup_location="top", has_menu=True, editor_options=None, **kwargs
    ):
        if editor_options is None:
            editor_options = {"style": "height: 50vh;"}
        super().__init__(
            **{
                "classes": "tcmap-horizontal bg-blue-grey-darken-2 d-flex align-center",
                **kwargs,
            }
        )
        self.server.enable_module(module)

        with self:
            if has_menu:
                with v3.VMenu(
                    v_model=f"{name}.menu",
                    activator="parent",
                    location=popup_location,
                    close_on_content_click=False,
                ):
                    ColorMapEditor(name, **editor_options)

            html.Div(
                f"{{{{ {name}.color_range && {name}.color_range[0] != null "
                f"? '' + {_fmt_expr(name, 0)} : '' }}}}",
                classes="text-caption px-2 text-no-wrap",
            )
            with html.Div(classes="tcmap-h-img-container rounded"):
                # Bottom independent band = values below minimum
                html.Div(
                    classes="tcmap-independent-band-h",
                    v_if=(
                        f"{name}.independent_bands === 'bottom'"
                        f" || {name}.independent_bands === 'both'"
                    ),
                    style=(
                        f"`background: rgba("
                        f"${{{name}.independent_band_bottom_color[0] * 255}}, "
                        f"${{{name}.independent_band_bottom_color[1] * 255}}, "
                        f"${{{name}.independent_band_bottom_color[2] * 255}}, "
                        f"${{{name}.independent_band_bottom_color[3]}});`",
                    ),
                )

                with html.Div(classes="tcmap-h-lut-container"):
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
                                "`top:0;left:${tick.position}%;"
                                "flex-direction:column;"
                                "transform:translateX(-50%);`",
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

                # Top independent band = values above maximum
                html.Div(
                    classes="tcmap-independent-band-h",
                    v_if=(
                        f"{name}.independent_bands === 'top'"
                        f" || {name}.independent_bands === 'both'"
                    ),
                    style=(
                        f"`background: rgba("
                        f"${{{name}.independent_band_top_color[0] * 255}}, "
                        f"${{{name}.independent_band_top_color[1] * 255}}, "
                        f"${{{name}.independent_band_top_color[2] * 255}}, "
                        f"${{{name}.independent_band_top_color[3]}});`",
                    ),
                )

            html.Div(
                f"{{{{ {name}.color_range && {name}.color_range[1] != null"
                f" ? {_fmt_expr(name, 1)} : '' }}}}",
                classes="text-caption px-2 text-no-wrap",
            )


class VerticalScalarBar(html.Div):
    def __init__(
        self, name, popup_location="top", has_menu=True, editor_options=None, **kwargs
    ):
        if editor_options is None:
            editor_options = {"style": "height: 50vh;"}
        super().__init__(
            **{
                "classes": (
                    "tcmap-vertical bg-blue-grey-darken-2 d-flex flex-column align-center"
                ),
                **kwargs,
            }
        )
        self.server.enable_module(module)

        with self:
            if has_menu:
                with v3.VMenu(
                    v_model=f"{name}.menu",
                    activator="parent",
                    location=popup_location,
                    close_on_content_click=False,
                ):
                    ColorMapEditor(name, **editor_options)

            # Max label at top
            html.Div(
                f"{{{{ {name}.color_range && {name}.color_range[1] != null"
                f" ? {_fmt_expr(name, 1)} : '' }}}}",
                classes="tcmap-vertical-labels text-caption text-no-wrap",
            )
            # Vertical LUT image stretched to fill
            with html.Div(classes="tcmap-v-img-container"):
                # Top independent band = values above maximum
                html.Div(
                    classes="tcmap-independent-band-v",
                    v_if=(
                        f"{name}.independent_bands === 'top'"
                        f" || {name}.independent_bands === 'both'"
                    ),
                    style=(
                        f"`background: rgba("
                        f"${{{name}.independent_band_top_color[0] * 255}}, "
                        f"${{{name}.independent_band_top_color[1] * 255}}, "
                        f"${{{name}.independent_band_top_color[2] * 255}}, "
                        f"${{{name}.independent_band_top_color[3]}});`",
                    ),
                )

                with html.Div(classes="tcmap-v-lut-container"):
                    html.Img(
                        src=(f"{name}.lut_img_v",),
                        draggable=False,
                    )
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

                # Bottom independent band = values below minimum
                html.Div(
                    classes="tcmap-independent-band-v",
                    v_if=(
                        f"{name}.independent_bands === 'bottom'"
                        f" || {name}.independent_bands === 'both'"
                    ),
                    style=(
                        f"`background: rgba("
                        f"${{{name}.independent_band_bottom_color[0] * 255}}, "
                        f"${{{name}.independent_band_bottom_color[1] * 255}}, "
                        f"${{{name}.independent_band_bottom_color[2] * 255}}, "
                        f"${{{name}.independent_band_bottom_color[3]}});`",
                    ),
                )

            # Min label at bottom
            html.Div(
                f"{{{{ {name}.color_range && {name}.color_range[0] != null"
                f" ? {_fmt_expr(name, 0)} : '' }}}}",
                classes="tcmap-vertical-labels text-caption text-no-wrap",
            )
