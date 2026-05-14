"""Colorbar display widget.

Renders a horizontal or vertical colorbar strip with:
- Range labels (min/max) on either side
- The LUT image stretched across the center
- Tick marks with labels and contrast-colored lines overlaid on the image
- Clicking the bar opens the control panel popup (VMenu)
"""

from trame.widgets import html
from trame.widgets import vuetify3 as v3

from trame_colormaps.widgets.control_panel import create_control_panel


def _fmt_expr(idx):
    """Return a JS expression that formats a color_range value compactly.

    - 0 → '0'
    - |v| >= 1000 or |v| < 0.01 → exponential with 1 decimal (e.g. '2.6e+2')
    - otherwise → up to 2 decimal places, trailing zeros stripped
    """
    val = f"config.color_range[{idx}]"
    return (
        f"(({val}) === 0 ? '0'"
        f" : (Math.abs({val}) >= 1000 || Math.abs({val}) < 0.01)"
        f"   ? ({val}).toExponential(1)"
        f"   : parseFloat(({val}).toFixed(2)))"
    )


def create_colorbar(config, update_color_preset, orientation=None):
    """Create a colorbar display with popup control panel.

    Each call creates an independent colorbar instance with its own
    scoped provide name and menu state variable.

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
    with config.provide_as("config"):
        if orientation == "horizontal":
            _horizontal_bar(config, update_color_preset)
        elif orientation == "vertical":
            _vertical_bar(config, update_color_preset)
        else:
            _horizontal_bar(config, update_color_preset)
            _vertical_bar(config, update_color_preset)


def _horizontal_bar(config, update_color_preset):
    """Horizontal colorbar layout."""
    with html.Div(
        classes="bg-blue-grey-darken-2 d-flex align-center",
        style="width:100%;height:1rem;user-select:none;cursor:context-menu;",
    ):
        with v3.VMenu(
            v_model="config.menu",
            activator="parent",
            location="top",
            close_on_content_click=False,
        ):
            create_control_panel(config, update_color_preset)
        _colorbar_content_h()


def _vertical_bar(config, update_color_preset):
    """Vertical colorbar layout."""
    with html.Div(
        classes="bg-blue-grey-darken-2 d-flex flex-column align-center",
        style="width:100%;height:100%;user-select:none;cursor:context-menu;",
    ):
        with v3.VMenu(
            v_model="config.menu",
            activator="parent",
            location="start",
            close_on_content_click=False,
        ):
            create_control_panel(config, update_color_preset)
        _colorbar_content_v()


def _colorbar_content_h():
    """Render the horizontal colorbar: labels, image strip, and tick marks."""
    html.Div(
        f"{{{{ config.color_range && config.color_range[0] != null ? {_fmt_expr(0)} : '' }}}}",
        classes="text-caption px-2 text-no-wrap",
    )
    with html.Div(
        classes="rounded w-100",
        style="height:70%;position:relative;",
    ):
        html.Img(
            src=("config.lut_img_h",),
            style="width:100%;height:2rem;",
            draggable=False,
        )
        with html.Div(
            style="position:absolute;top:0;left:0;right:0;bottom:0;pointer-events:none;",
        ):
            with html.Div(
                v_for="(tick, i) in config.color_ticks",
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
        f"{{{{ config.color_range && config.color_range[1] != null ? {_fmt_expr(1)} : '' }}}}",
        classes="text-caption px-2 text-no-wrap",
    )


def _colorbar_content_v():
    """Render the vertical colorbar: labels, rotated image strip, and tick marks.

    Max is at the top, min at the bottom.
    """
    # Max label at top
    html.Div(
        f"{{{{ config.color_range && config.color_range[1] != null ? {_fmt_expr(1)} : '' }}}}",
        classes="text-caption py-1 text-no-wrap",
        style="font-size:0.55rem;writing-mode:horizontal-tb;",
    )
    # Vertical LUT image (1px wide, stretched to fill)
    with html.Div(
        style="flex:1;width:100%;position:relative;min-height:0;",
    ):
        html.Img(
            src=("config.lut_img_v",),
            style="width:100%;height:100%;",
            draggable=False,
        )
        # Tick overlay
        with html.Div(
            style="position:absolute;top:0;left:0;right:0;bottom:0;pointer-events:none;",
        ):
            with html.Div(
                v_for="(tick, i) in config.color_ticks",
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
        f"{{{{ config.color_range && config.color_range[0] != null ? {_fmt_expr(0)} : '' }}}}",
        classes="text-caption py-1 text-no-wrap",
        style="font-size:0.55rem;writing-mode:horizontal-tb;",
    )
