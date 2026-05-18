"""
Trame module definition for trame-colormaps.

This package load a custom css to reduce the verbosity of the widget templates
"""

from pathlib import Path

from trame_colormaps import __version__

serve_path = str(Path(__file__).with_name("serve").resolve())
serve = {f"__trame_colormaps_{__version__}": serve_path}
styles = [f"__trame_colormaps_{__version__}/style.css"]


def setup(server, **_):
    """Complain if server is not vue3"""
    if server.client_type != "vue3":
        msg = f"Server using client_type='{server.client_type}' while we expect 'vue3'"
        raise TypeError(msg)
