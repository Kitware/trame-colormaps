"""Colormap widgets and controllers for trame."""

from trame_colormaps.colorbar import Colorbar, create_colorbar
from trame_colormaps.control_panel import ControlPanel, create_control_panel
from trame_colormaps.controller import ColormapController
from trame_colormaps.state import ColormapConfig

__all__ = [
    "Colorbar",
    "ColormapConfig",
    "ColormapController",
    "ControlPanel",
    "create_colorbar",
    "create_control_panel",
]
