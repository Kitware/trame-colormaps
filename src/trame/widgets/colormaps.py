"""Trame widget entry point for trame-colormaps.

Re-exports all widget classes (ColorMapEditor, HorizontalScalarBar,
VerticalScalarBar) and registers the module with the trame server.
"""

from trame_colormaps.widgets import *  # noqa: F403


def initialize(server):
    """Called automatically by trame when this widget module is imported."""
    from trame_colormaps import module  # noqa: PLC0415

    server.enable_module(module)
