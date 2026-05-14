"""Colormap configuration state model.

Self-contained state for a single colormap instance, including preset name,
scale mode, range, discrete settings, and derived display data (lut_img_h/v, ticks).

Can be used standalone or composed into a larger application config.
When used standalone, instantiate ColormapConfig directly.  When composed
into an existing config, pass that config object to ColormapController
instead.
"""

from trame.app import dataclass

from trame_colormaps.core.presets import DEFAULT_PRESETS


class ColormapConfig(dataclass.StateDataModel):
    """Reactive state model for a single colormap instance.

    All fields are synced to the Trame client via ``dataclass.Sync``.
    Use this standalone when the colormaps module owns its own state,
    or compose these same fields into a larger application config and
    pass that object to ``ColormapController`` instead.

    Fields fall into three groups:

    **User-settable** — bound to UI controls, read by the controller:

    - ``active_presets``: List of preset names available in the picker.
    - ``preset``: Active color preset name.
    - ``invert``: Flip the color transfer function.
    - ``color_blind``: Filter the preset list to color-blind safe only.
    - ``use_log_scale``: Scale mode — ``"linear"``, ``"log"``, or ``"symlog"``.
    - ``discrete_log``: Enable discrete (stepped) color banding.
    - ``n_discrete_colors``: Number of sub-bands per interval (1–20).
    - ``n_intervals``: Number of equal intervals for discrete linear mode.
    - ``n_ticks``: Desired number of tick marks on the colorbar.
    - ``color_value_min`` / ``color_value_max``: Manual range strings
      entered in the text fields.
    - ``override_range``: When True, use the manual strings instead of
      the data-derived range.

    **Derived** — written by the controller, consumed by UI:

    - ``color_range``: Active (min, max) as floats, either from data or
      parsed from the manual strings.
    - ``color_value_min_valid`` / ``color_value_max_valid``: Whether the
      corresponding manual string parses as a valid float.
    - ``n_colors``: Number of LUT samples (default 255).
    - ``lut_img_h``: Base64 PNG data URI of the horizontal colorbar image.
    - ``lut_img_v``: Base64 PNG data URI of the vertical colorbar image.
    - ``color_ticks``: List of ``{position, label, color}`` dicts for
      tick marks overlaid on the colorbar.
    - ``effective_color_range``: Actual CTF range after transforms
      (may differ from ``color_range`` for log/symlog).
    - ``luts_normal``: Sorted list of ``{name, url, safe}`` dicts for
      the preset picker (normal orientation).
    - ``luts_inverted``: Same as ``luts_normal`` but with inverted images.

    **UI widget state** — used by the control panel popup:

    - ``menu``: Whether the preset control panel is open.
    - ``search``: Preset search/filter text.
    """

    # --- User-settable (bound to UI, read by controller) ---
    active_presets: list[str] = dataclass.Sync(list, DEFAULT_PRESETS)
    preset: str = dataclass.Sync(str, "BuGnYl")
    invert: bool = dataclass.Sync(bool, False)
    color_blind: bool = dataclass.Sync(bool, False)
    use_log_scale: str = dataclass.Sync(str, "linear")
    discrete_log: bool = dataclass.Sync(bool, False)
    n_discrete_colors: int = dataclass.Sync(int, 4)
    n_intervals: int = dataclass.Sync(int, 4)
    n_ticks: int = dataclass.Sync(int, 5)
    color_value_min: str = dataclass.Sync(str, "0")
    color_value_max: str = dataclass.Sync(str, "1")
    override_range: bool = dataclass.Sync(bool, False)

    # --- Derived (written by controller, read by UI) ---
    color_value_min_valid: bool = dataclass.Sync(bool, True)
    color_value_max_valid: bool = dataclass.Sync(bool, True)
    color_range: list[float] = dataclass.Sync(tuple[float, float], (0, 1))
    n_colors: int = dataclass.Sync(int, 255)
    lut_img_h: str = dataclass.Sync(str)
    lut_img_v: str = dataclass.Sync(str)
    color_ticks: list = dataclass.Sync(list, list)
    effective_color_range: list[float] = dataclass.Sync(tuple[float, float], (0, 1))
    luts_normal: list = dataclass.Sync(list, list)
    luts_inverted: list = dataclass.Sync(list, list)

    # --- UI widget state (control panel popup) ---
    menu: bool = dataclass.Sync(bool, False)
    search: str | None = dataclass.Sync(str)
    orientation: str = dataclass.Sync(str, "horizontal")
