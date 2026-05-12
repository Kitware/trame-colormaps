"""Colorbar display widget.

Renders a horizontal colorbar strip with:
- Range labels (min/max) on either side
- The LUT image stretched across the center
- Tick marks with labels and contrast-colored lines overlaid on the image
- Clicking the bar opens the control panel popup

Supports both Vuetify 2 and Vuetify 3 — detected automatically.
Vue 3 uses a VMenu with ``activator="parent"``; Vue 2 uses a plain
positioned div toggled via ``v-show`` (because ``trame-dataclass``'s
``provide_as`` scoped slot is Vue 3 only).
"""

import itertools

from trame.widgets import html

from trame_colormaps.widgets._compat import vuetify, is_v3, v2_state_prefix
from trame_colormaps.widgets.control_panel import create_control_panel

_instance_counter = itertools.count()


def _fmt_expr(p, idx):
    """Return a JS expression that formats a color_range value compactly.

    - 0 → '0'
    - |v| >= 1000 or |v| < 0.01 → exponential with 1 decimal (e.g. '2.6e+2')
    - otherwise → up to 2 decimal places, trailing zeros stripped
    """
    v = f"{p}color_range[{idx}]"
    return (
        f"(({v}) === 0 ? '0'"
        f" : (Math.abs({v}) >= 1000 || Math.abs({v}) < 0.01)"
        f"   ? ({v}).toExponential(1)"
        f"   : parseFloat(({v}).toFixed(2)))"
    )


def create_colorbar(config, update_color_preset, orientation=None):
    """Create a colorbar display with popup control panel.

    Each call creates an independent colorbar instance with its own
    scoped provide name (Vue 3) and menu state variable.

    Args:
        config: ColormapConfig (or compatible StateDataModel) with colormap
            fields. See ``ColormapConfig`` docstring for required fields.
        update_color_preset: Callback for preset changes — typically
            ``ColormapController.update_color_preset``.
        orientation: ``"horizontal"``, ``"vertical"``, or ``None`` (default).
            When set, only that orientation's DOM is emitted (use separate
            calls placed in different layout regions).  When ``None``, both
            orientations are emitted with ``v-if`` toggling.
    """
    v = vuetify()
    v3_mode = is_v3()
    inst = next(_instance_counter)

    if v3_mode:
        p = "config."
        with config.provide_as("config"):
            _colorbar_body(v, v3_mode, p, config, update_color_preset, orientation, inst)
    else:
        pfx = v2_state_prefix(config, prefix=f"cb{inst}")
        p = f"{pfx}_"
        _colorbar_body(v, v3_mode, p, config, update_color_preset, orientation, inst)


def _colorbar_body(v, v3_mode, p, config, update_color_preset, orientation, inst):
    """Shared colorbar layout.  *p* is the variable prefix for templates."""
    bar_bg = (
        "bg-blue-grey-darken-2"
        if v3_mode
        else "blue-grey darken-2"
    )
    menu_var = f"{p}menu"

    if orientation == "horizontal":
        _horizontal_bar(v, v3_mode, p, config, update_color_preset, bar_bg, menu_var)
    elif orientation == "vertical":
        _vertical_bar(v, v3_mode, p, config, update_color_preset, bar_bg, menu_var)
    else:
        # Both — use v-if so only one is in the DOM at a time.
        _horizontal_bar(v, v3_mode, p, config, update_color_preset, bar_bg, menu_var)
        _vertical_bar(v, v3_mode, p, config, update_color_preset, bar_bg, menu_var)


def _horizontal_bar(v, v3_mode, p, config, update_color_preset, bar_bg, menu_var):
    """Horizontal colorbar layout."""
    bar_classes = f"{bar_bg} d-flex align-center"

    if v3_mode:
        with html.Div(
            classes=bar_classes,
            style="width:100%;height:1rem;user-select:none;cursor:context-menu;",
        ):
            with v.VMenu(
                v_model=menu_var,
                activator="parent",
                location="top",
                close_on_content_click=False,
            ):
                create_control_panel(config, update_color_preset, p)
            _colorbar_content_h(v, p)
    else:
        with html.Div(
            v_show=menu_var,
            style="position:fixed;bottom:1rem;left:0;z-index:10;",
        ):
            create_control_panel(config, update_color_preset, p)
        with html.Div(
            classes=bar_classes,
            style="height:1rem;user-select:none;cursor:context-menu;",
            click=f"{menu_var} = !{menu_var}",
        ):
            _colorbar_content_h(v, p)


def _vertical_bar(v, v3_mode, p, config, update_color_preset, bar_bg, menu_var):
    """Vertical colorbar layout."""
    bar_classes = f"{bar_bg} d-flex flex-column align-center"

    if v3_mode:
        with html.Div(
            classes=bar_classes,
            style="width:100%;height:100%;user-select:none;cursor:context-menu;",
        ):
            with v.VMenu(
                v_model=menu_var,
                activator="parent",
                location="start",
                close_on_content_click=False,
            ):
                create_control_panel(config, update_color_preset, p)
            _colorbar_content_v(v, p)
    else:
        with html.Div(
            v_show=menu_var,
            style="position:fixed;bottom:1rem;right:3rem;z-index:10;",
        ):
            create_control_panel(config, update_color_preset, p)
        with html.Div(
            classes=bar_classes,
            style="width:100%;height:100%;user-select:none;cursor:context-menu;",
            click=f"{menu_var} = !{menu_var}",
        ):
            _colorbar_content_v(v, p)


def _colorbar_content_h(v, p):
    """Render the horizontal colorbar: labels, image strip, and tick marks.

    *p* is ``"config."`` (Vue 3) or ``"config_"`` (Vue 2).
    """
    html.Div(
        f"{{{{ {p}color_range && {p}color_range[0] != null ? {_fmt_expr(p, 0)} : '' }}}}",
        classes="text-caption px-2 text-no-wrap",
    )
    with html.Div(
        classes="rounded w-100",
        style="height:70%;position:relative;",
    ):
        html.Img(
            src=(f"{p}lut_img_h",),
            style="width:100%;height:2rem;",
            draggable=False,
        )
        with html.Div(
            style="position:absolute;top:0;left:0;right:0;bottom:0;pointer-events:none;",
        ):
            with html.Div(
                v_for=f"(tick, i) in {p}color_ticks",
                key="i",
                style=(
                    "`position:absolute;left:${tick.position}%;top:0;height:100%;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center;`",
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
        f"{{{{ {p}color_range && {p}color_range[1] != null ? {_fmt_expr(p, 1)} : '' }}}}",
        classes="text-caption px-2 text-no-wrap",
    )


def _colorbar_content_v(v, p):
    """Render the vertical colorbar: labels, rotated image strip, and tick marks.

    Max is at the top, min at the bottom.
    *p* is ``"config."`` (Vue 3) or ``"config_"`` (Vue 2).
    """
    # Max label at top
    html.Div(
        f"{{{{ {p}color_range && {p}color_range[1] != null ? {_fmt_expr(p, 1)} : '' }}}}",
        classes="text-caption py-1 text-no-wrap",
        style="font-size:0.55rem;writing-mode:horizontal-tb;",
    )
    # Vertical LUT image (1px wide, stretched to fill)
    with html.Div(
        style="flex:1;width:100%;position:relative;min-height:0;",
    ):
        html.Img(
            src=(f"{p}lut_img_v",),
            style="width:100%;height:100%;",
            draggable=False,
        )
        # Tick overlay
        with html.Div(
            style="position:absolute;top:0;left:0;right:0;bottom:0;pointer-events:none;",
        ):
            with html.Div(
                v_for=f"(tick, i) in {p}color_ticks",
                key="i",
                style=(
                    "`position:absolute;top:${100 - tick.position}%;left:0;width:100%;transform:translateY(-50%);display:flex;flex-direction:row;align-items:center;`",
                ),
            ):
                html.Div(
                    style=(
                        "`height:1.5px;width:30%;background:${tick.color};`",
                    ),
                )
                html.Span(
                    "{{ tick.label }}",
                    style=(
                        "`font-size:0.5rem;line-height:1;white-space:nowrap;color:${tick.color};`",
                    ),
                )
    # Min label at bottom
    html.Div(
        f"{{{{ {p}color_range && {p}color_range[0] != null ? {_fmt_expr(p, 0)} : '' }}}}",
        classes="text-caption py-1 text-no-wrap",
        style="font-size:0.55rem;writing-mode:horizontal-tb;",
    )
