"""Colorbar: self-contained colorbar with config, controller, and UI.

Also provides the lower-level ``create_colorbar`` function and the
internal rendering helpers for horizontal and vertical colorbar strips.
"""

import itertools

from trame.widgets import html
from trame.widgets import vuetify3 as v3

from trame_colormaps.controller import ColormapController
from trame_colormaps.state import ColormapConfig
from trame_colormaps.control_panel import ControlPanel, create_control_panel

# Each Colorbar gets a unique ID so its menu state key is distinct.
# The registry tracks all instances so opening one panel can close the others.
_colorbar_counter = itertools.count()
_all_colorbars = []


class Colorbar:
    """A self-contained colorbar with its own config, controller, and UI.

    Args:
        server: Trame server instance.
        variable_name: Name of the scalar array to color by.
        mapper: VTK mapper to wire the color transfer function to.
        data_array_fn: Callable returning the VTK data array.
        render_fn: Callable to trigger a render after changes.
        orientation: ``"horizontal"`` or ``"vertical"``.
        scalar_mode: ``"default"``, ``"point"``, or ``"cell"``.
        config: Optional existing ColormapConfig to reuse.
        popup_location: Where the control panel pops up relative to the bar.
            ``"top"``, ``"bottom"``, ``"start"``, ``"end"``.
            Defaults to ``"top"`` for horizontal, ``"end"`` for vertical.
    """

    def __init__(
        self,
        server,
        variable_name,
        mapper,
        data_array_fn,
        render_fn,
        orientation="horizontal",
        scalar_mode="default",
        config=None,
        popup_location=None,
    ):
        self._id = next(_colorbar_counter)
        self._orientation = orientation
        self._server = server
        self._popup_location = popup_location or ("top" if orientation == "horizontal" else "end")

        self.config = config if config is not None else ColormapConfig(server)
        self.controller = ColormapController(
            server=server,
            variable_name=variable_name,
            mapper=mapper,
            data_array_fn=data_array_fn,
            render_fn=render_fn,
            config=self.config,
            scalar_mode=scalar_mode,
        )

        self.panel = ControlPanel(self.config, self.controller.update_color_preset)

        # Register for close-others behavior
        _all_colorbars.append(self)

        self._menu_state_key = f"cb{self._id}_menu"

        # Close other panels when this one opens
        @server.state.change(self._menu_state_key)
        def _close_others(**kwargs):
            if kwargs.get(self._menu_state_key):
                for cb in _all_colorbars:
                    if cb is not self and cb.config.menu:
                        cb.config.menu = False

    def render(self):
        """Emit the colorbar DOM into the current trame layout context."""
        with self.config.provide_as("config"):
            _render_bar(
                self._orientation,
                self._popup_location,
                lambda: self.panel.render(),
            )


def create_colorbar(config, update_color_preset, orientation=None, popup_location=None):
    """Emit a colorbar into the current trame layout context.

    Use this instead of ``Colorbar`` when colormap fields are composed
    into a larger application config (e.g. a ``ViewConfiguration`` that
    includes layout fields alongside colormap fields) rather than using
    a standalone ``ColormapConfig``.  The caller is responsible for
    creating the ``ColormapController`` and wiring the mapper.

    Args:
        config: Any ``StateDataModel`` that contains the colormap fields
            defined in ``ColormapConfig``.  Does not need to be a
            ``ColormapConfig`` instance.
        update_color_preset: Callback for preset changes — typically
            ``ColormapController.update_color_preset``.
        orientation: ``"vertical"`` for a vertical bar, anything else
            (including ``None``) defaults to horizontal.
        popup_location: ``"top"``, ``"bottom"``, ``"start"``, ``"end"``.
            Defaults to ``"top"`` for horizontal, ``"start"`` for vertical.
    """
    orient = orientation or "horizontal"
    location = popup_location or ("top" if orient == "horizontal" else "start")
    with config.provide_as("config"):
        _render_bar(
            orient,
            location,
            lambda: create_control_panel(config, update_color_preset),
        )


# ---------------------------------------------------------------------------
# Internal rendering helpers
# ---------------------------------------------------------------------------


def _render_bar(orientation, popup_location, panel_render_fn):
    """Shared bar layout: outer div, VMenu with panel, and colorbar content."""
    is_h = orientation == "horizontal"

    if is_h:
        classes = "bg-blue-grey-darken-2 d-flex align-center"
        style = "width:100%;height:1rem;user-select:none;cursor:context-menu;"
    else:
        classes = "bg-blue-grey-darken-2 d-flex flex-column align-center"
        style = "width:1rem;height:100%;user-select:none;cursor:context-menu;"

    with html.Div(classes=classes, style=style):
        with v3.VMenu(
            v_model="config.menu",
            activator="parent",
            location=popup_location,
            close_on_content_click=False,
        ):
            panel_render_fn()
        if is_h:
            _colorbar_content_h()
        else:
            _colorbar_content_v()


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
    """Render the vertical colorbar — like horizontal rotated -90°.

    Max is at the top, min at the bottom.  Labels and ticks use
    writing-mode:vertical-lr + rotate(180deg) so text reads bottom-to-top.
    """
    # Max label at top
    html.Div(
        f"{{{{ config.color_range && config.color_range[1] != null ? {_fmt_expr(1)} : '' }}}}",
        classes="text-caption text-no-wrap",
        style="font-size:0.5rem;writing-mode:vertical-lr;transform:rotate(180deg);padding:2px 0;",
    )
    # Vertical LUT image stretched to fill
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
                    "`position:absolute;top:${100 - tick.position}%;left:0;width:100%;transform:translateY(-50%);display:flex;flex-direction:column;align-items:center;`",
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
                        "`font-size:0.5rem;line-height:1;white-space:nowrap;color:${tick.color};writing-mode:vertical-lr;transform:rotate(180deg);`",
                    ),
                )
                html.Div(
                    style=("`height:1.5px;flex:1;background:${tick.color};`",),
                )
    # Min label at bottom
    html.Div(
        f"{{{{ config.color_range && config.color_range[0] != null ? {_fmt_expr(0)} : '' }}}}",
        classes="text-caption text-no-wrap",
        style="font-size:0.5rem;writing-mode:vertical-lr;transform:rotate(180deg);padding:2px 0;",
    )
