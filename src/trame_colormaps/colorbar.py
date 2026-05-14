"""Self-contained Colorbar object.

Each instance owns its own ColormapConfig, ColormapController, and renders
its own DOM.  Multiple Colorbar instances are fully independent unless
they share the same mapper.
"""

import itertools

from trame.widgets import html

from trame_colormaps.controller import ColormapController
from trame_colormaps.state import ColormapConfig
from trame.widgets import vuetify3 as v3
from trame_colormaps.widgets.colorbar import _colorbar_content_h, _colorbar_content_v
from trame_colormaps.widgets.control_panel import ControlPanel

_colorbar_counter = itertools.count()
_all_colorbars = []  # registry of all Colorbar instances


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
        if popup_location is None:
            self._popup_location = "top" if orientation == "horizontal" else "end"
        else:
            self._popup_location = popup_location

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
        is_h = self._orientation == "horizontal"

        if is_h:
            bar_classes = "bg-blue-grey-darken-2 d-flex align-center"
            bar_style = "width:100%;height:1rem;user-select:none;cursor:context-menu;"
        else:
            bar_classes = "bg-blue-grey-darken-2 d-flex flex-column align-center"
            bar_style = "width:100%;height:100%;user-select:none;cursor:context-menu;"

        with self.config.provide_as("config"):
            with html.Div(classes=bar_classes, style=bar_style):
                with v3.VMenu(
                    v_model="config.menu",
                    activator="parent",
                    location=self._popup_location,
                    close_on_content_click=False,
                ):
                    self.panel.render()
                if is_h:
                    _colorbar_content_h()
                else:
                    _colorbar_content_v()
