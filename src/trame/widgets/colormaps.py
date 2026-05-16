from trame_colormaps.widgets import *  # noqa: F403


def initialize(server):
    from trame_colormaps import module  # noqa: PLC0415

    server.enable_module(module)
