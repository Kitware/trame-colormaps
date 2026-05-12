"""Self-contained Colorbar object.

Each instance owns its own ColormapConfig, ColormapController, and renders
its own DOM.  Multiple Colorbar instances are fully independent unless
they share the same mapper.
"""

import itertools

from trame.widgets import html

from trame_colormaps.controller import ColormapController
from trame_colormaps.state import ColormapConfig
from trame_colormaps.widgets._compat import vuetify, is_v3, v2_state_prefix
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
            Vuetify 3 location values: ``"top"``, ``"bottom"``, ``"start"``,
            ``"end"``.  Defaults to ``"top"`` for horizontal, ``"end"`` for
            vertical.
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
        # Pre-compute Vue 2 state prefix (sets up watchers once).
        # Must happen before ControlPanel so flush fns exist.
        self._v2_prefix = v2_state_prefix(self.config, prefix=f"cb{self._id}")

        # Wrap the controller callback so Vue 2 state mirror is flushed
        # after every update (trame-dataclass watch doesn't fire from
        # server-side attribute assignments).
        _orig_update = self.controller.update_color_preset
        _updating = {"active": False}

        def _flush():
            for fn in getattr(self.config, "_v2_flush_fns", []):
                fn()

        def _update_and_flush(*args, **kwargs):
            if _updating["active"]:
                return
            _updating["active"] = True
            try:
                _orig_update(*args, **kwargs)
                _flush()
            finally:
                _updating["active"] = False

        self._update_and_flush = _update_and_flush
        self.panel = ControlPanel(self.config, _update_and_flush)

        # For Vue 2: config.watch doesn't fire from server-side attribute
        # assignments, so replicate the controller's config watchers using
        # server state watchers on the mirrored variables.
        pfx = f"cb{self._id}"
        preset_keys = [
            f"{pfx}_preset", f"{pfx}_invert", f"{pfx}_use_log_scale",
            f"{pfx}_discrete_log", f"{pfx}_n_discrete_colors",
            f"{pfx}_n_intervals", f"{pfx}_n_ticks",
        ]

        @server.state.change(*preset_keys)
        def _v2_on_preset_fields(**kwargs):
            _update_and_flush(
                self.config.preset,
                self.config.invert,
                self.config.use_log_scale,
                self.config.discrete_log,
                self.config.n_discrete_colors,
                self.config.n_intervals,
                self.config.n_ticks,
            )

        range_keys = [f"{pfx}_override_range", f"{pfx}_color_range"]

        @server.state.change(*range_keys)
        def _v2_on_range_fields(**kwargs):
            if _updating["active"]:
                return
            _updating["active"] = True
            try:
                self.controller.update_color_range()
                _flush()
            finally:
                _updating["active"] = False

        @server.state.change(f"{pfx}_active_presets")
        def _v2_on_active_presets(**kwargs):
            if _updating["active"]:
                return
            _updating["active"] = True
            try:
                self.controller._build_lut_lists(self.config.active_presets)
                _flush()
            finally:
                _updating["active"] = False

        # Register for close-others behavior
        _all_colorbars.append(self)

        self._menu_state_key = f"cb{self._id}_menu"

        # Close other panels when this one opens (works for both v2 and v3
        # because v2_state_prefix mirrors config.menu ↔ cbN_menu).
        @server.state.change(self._menu_state_key)
        def _close_others(**kwargs):
            if kwargs.get(self._menu_state_key):
                for cb in _all_colorbars:
                    if cb is not self and cb.config.menu:
                        cb.config.menu = False

    def _close_others_js(self):
        """Return JS that sets all other colorbars' menu state vars to false."""
        parts = []
        for cb in _all_colorbars:
            if cb is not self:
                parts.append(f"{cb._menu_state_key} = false")
        return "; ".join(parts)

    def render(self):
        """Emit the colorbar DOM into the current trame layout context."""
        v = vuetify()
        v3_mode = is_v3()

        bar_bg = (
            "bg-blue-grey-darken-2"
            if v3_mode
            else "blue-grey darken-2"
        )

        if v3_mode:
            p = "config."
            menu_var = f"{p}menu"
            with self.config.provide_as("config"):
                self._render_bar_v3(v, p, bar_bg, menu_var)
        else:
            p = f"{self._v2_prefix}_"
            menu_var = self._menu_state_key
            self._render_bar_v2(v, p, bar_bg, menu_var)

    def _render_bar_v3(self, v, p, bar_bg, menu_var):
        """Render the bar for Vue 3 using VMenu with activator='parent'."""
        is_h = self._orientation == "horizontal"

        if is_h:
            bar_classes = f"{bar_bg} d-flex align-center"
            bar_style = "width:100%;height:1rem;user-select:none;cursor:context-menu;"
        else:
            bar_classes = f"{bar_bg} d-flex flex-column align-center"
            bar_style = "width:100%;height:100%;user-select:none;cursor:context-menu;"

        with html.Div(classes=bar_classes, style=bar_style):
            with v.VMenu(
                v_model=menu_var,
                activator="parent",
                location=self._popup_location,
                close_on_content_click=False,
            ):
                self.panel.render(p)
            if is_h:
                _colorbar_content_h(v, p)
            else:
                _colorbar_content_v(v, p)

    def _render_bar_v2(self, v, p, bar_bg, menu_var):
        """Render the bar for Vue 2 with manual popup positioning."""
        is_h = self._orientation == "horizontal"

        if is_h:
            bar_classes = f"{bar_bg} d-flex align-center"
            bar_style = "width:100%;height:1rem;user-select:none;cursor:context-menu;"
        else:
            bar_classes = f"{bar_bg} d-flex flex-column align-center"
            bar_style = "width:100%;height:100%;user-select:none;cursor:context-menu;"

        close_others = self._close_others_js()
        toggle_js = f"{close_others}; {menu_var} = !{menu_var}" if close_others else f"{menu_var} = !{menu_var}"

        pos_map = {
            "top": "bottom:100%;left:0;",
            "bottom": "top:100%;left:0;",
            "start": "right:100%;top:0;",
            "end": "left:100%;top:0;",
        }
        panel_pos = pos_map.get(self._popup_location, "bottom:100%;left:0;")
        with html.Div(style="position:relative;height:100%;"):
            with html.Div(
                v_show=menu_var,
                style=f"position:absolute;{panel_pos}z-index:10;",
            ):
                self.panel.render(p)
            with html.Div(
                classes=bar_classes,
                style=bar_style,
                click=toggle_js,
            ):
                if is_h:
                    _colorbar_content_h(v, p)
                else:
                    _colorbar_content_v(v, p)
