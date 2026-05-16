"""Colormap configuration state model.

Self-contained state for a single colormap instance, including preset name,
scale mode, range, discrete settings, and derived display data (lut_img_h/v, ticks).

Can be used standalone or composed into a larger application config.
When used standalone, instantiate ColormapConfig directly.  When composed
into an existing config, pass that config object to ColormapController
instead.
"""

import math

import numpy as np
from trame.app.dataclass import ServerOnly, StateDataModel, Sync, get_instance, watch
from vtkmodules.util.numpy_support import vtk_to_numpy
from vtkmodules.vtkRenderingCore import vtkColorTransferFunction

from trame_colormaps.core.presets import (
    COLOR_BLIND_SAFE,
    COLORBAR_CACHE,
    DEFAULT_PRESETS,
    get_rgb_points,
    lut_to_img_h,
    lut_to_img_v,
    rescale_ctf,
)
from trame_colormaps.core.ticks import (
    format_log_tick,
    format_tick,
    get_nice_ticks,
    tick_contrast_color,
)
from trame_colormaps.core.transforms import (
    apply_discrete_linear,
    apply_discrete_log,
    apply_discrete_symlog,
    apply_linear,
    apply_log,
    apply_symlog,
    calculate_linthresh,
)

ALL_COLORMAP_CONFIGS = []

__all__ = ["ColormapConfig"]


class ColormapConfig(StateDataModel):
    """Reactive state model for a single colormap instance.

    All fields are synced to the Trame client via ``Sync``.
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
    - ``n_discrete_colors``: Number of color bands between ticks (linear)
      or per decade (log/symlog).
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
    active_presets: list[str] = Sync(list, DEFAULT_PRESETS)
    preset: str = Sync(str, "BuGnYl")
    invert: bool = Sync(bool, False)
    color_blind: bool = Sync(bool, False)
    use_log_scale: str = Sync(str, "linear")
    discrete_log: bool = Sync(bool, False)
    n_discrete_colors: int = Sync(int, 4)
    n_ticks: int = Sync(int, 5)
    color_value_min: str = Sync(str, "0")
    color_value_max: str = Sync(str, "1")
    override_range: bool = Sync(bool, False)

    # --- Derived (written by controller, read by UI) ---
    color_value_min_valid: bool = Sync(bool, True)
    color_value_max_valid: bool = Sync(bool, True)
    color_range: list[float] = Sync(tuple[float, float], (0, 1))
    n_colors: int = Sync(int, 255)
    lut_img_h: str = Sync(str)
    lut_img_v: str = Sync(str)
    color_ticks: list = Sync(list, list)
    effective_color_range: list[float] = Sync(tuple[float, float], (0, 1))
    luts_normal: list = Sync(list, list)
    luts_inverted: list = Sync(list, list)

    # --- UI widget state (control panel popup) ---
    menu: bool = Sync(bool, False)
    search: str | None = Sync(str)
    orientation: str = Sync(str, "horizontal")
    mapper_change: int = ServerOnly(int, 0)

    def __init__(self, *args, mapper=None, data_array_fn=None, **kwargs):
        # Create and own the CTF
        self._ctf = vtkColorTransferFunction()
        self._mapper = mapper
        self._get_data_array = data_array_fn

        if self._mapper:
            self._mapper.SetLookupTable(self._ctf)
            self._mapper.SetUseLookupTableScalarRange(True)

        super().__init__(*args, **kwargs)
        ALL_COLORMAP_CONFIGS.append(self._id)

    # --- Internal reactive ---

    @watch("menu")
    def hide_other_menus_on_open(self, show):
        if not show:
            return

        other_colormaps = [
            get_instance(_id)
            for _id in ALL_COLORMAP_CONFIGS
            if _id != self._id and get_instance(_id) is not None
        ]
        for colormap in other_colormaps:
            if colormap.menu:
                colormap.menu = False

    @watch("color_value_min", "color_value_max")
    def _on_range_str_change(self, color_value_min, color_value_max):
        """Validate min/max strings and update color_range if both are valid."""
        try:
            min_value = float(color_value_min)
            self.color_value_min_valid = not math.isnan(min_value)
        except ValueError:
            self.color_value_min_valid = False

        try:
            max_value = float(color_value_max)
            self.color_value_max_valid = not math.isnan(max_value)
        except ValueError:
            self.color_value_max_valid = False

        if self.color_value_min_valid and self.color_value_max_valid:
            self.color_range = (min_value, max_value)

    @watch("override_range", "color_range", eager=True)
    def _on_range_change(self, *_):
        """Reactive handler for override_range or color_range changes."""
        self.update_color_range()

    @watch("active_presets", eager=True)
    def _build_lut_lists(self, active_presets):
        """Rebuild the sorted preset picker lists from active_presets.

        Filters COLORBAR_CACHE by the given preset names and populates
        ``config.luts_normal`` and ``config.luts_inverted``.

        Args:
            active_presets: List of preset names to include.
        """
        allowed = set(active_presets) if active_presets else set(COLORBAR_CACHE.keys())
        luts_normal = [
            {"name": k, "url": v["normal"], "safe": k in COLOR_BLIND_SAFE}
            for k, v in COLORBAR_CACHE.items()
            if k in allowed
        ]
        luts_inverted = [
            {"name": k, "url": v["inverted"], "safe": k in COLOR_BLIND_SAFE}
            for k, v in COLORBAR_CACHE.items()
            if k in allowed
        ]
        luts_normal.sort(key=lambda e: e["name"].lower())
        luts_inverted.sort(key=lambda e: e["name"].lower())
        self.luts_normal = luts_normal
        self.luts_inverted = luts_inverted

    def _compute_ticks(self, linthresh=None, linear_rgb_points=None, n_ticks=5):
        """Compute tick positions, labels, and contrast colors for the colorbar.

        Args:
            linthresh: Linear threshold for log/symlog scale (None for linear).
            linear_rgb_points: RGB control points from the linear CTF, used to
                sample contrast colors. Falls back to current CTF points.
            n_ticks: Desired number of tick marks (all scale modes).
        """
        vmin, vmax = self.color_range

        data_range = vmax - vmin
        ticks = []
        if data_range > 0:
            if self.use_log_scale == "linear":
                tick_vals = get_nice_ticks(vmin, vmax, n_ticks, scale="linear")
                for val in tick_vals:
                    pos = (val - vmin) / data_range * 100
                    ticks.append({"position": round(pos, 2), "label": format_tick(val)})
            elif self.use_log_scale in ("log", "symlog"):
                lt = linthresh if linthresh is not None else 1.0

                def _sl(v):
                    return np.sign(v) * np.log10(1.0 + np.abs(v) / lt)

                sl_min = float(_sl(vmin))
                sl_max = float(_sl(vmax))
                sl_range = sl_max - sl_min
                tick_vals = get_nice_ticks(
                    vmin,
                    vmax,
                    n_ticks,
                    scale=self.use_log_scale,
                    linthresh=linthresh,
                )
                for val in tick_vals:
                    if sl_range > 0:
                        pos = (float(_sl(val)) - sl_min) / sl_range * 100
                    else:
                        pos = (val - vmin) / data_range * 100
                    ticks.append(
                        {"position": round(pos, 2), "label": format_log_tick(val)}
                    )

        # Sample colors from the *linear* CTF so tick contrast matches the
        # displayed colorbar image, not the log/symlog-remapped rendering CTF.
        rgb_points = (
            linear_rgb_points if linear_rgb_points else get_rgb_points(self._ctf)
        )
        if len(rgb_points) < 4:
            self.color_ticks = []
            return
        img_min = rgb_points[0]
        img_max = rgb_points[-4]
        img_range = img_max - img_min
        if img_range == 0:
            self.color_ticks = []
            return

        # Build a temporary linear CTF to sample tick contrast colors
        linear_ctf = vtkColorTransferFunction()
        for i in range(0, len(rgb_points), 4):
            linear_ctf.AddRGBPoint(
                rgb_points[i],
                rgb_points[i + 1],
                rgb_points[i + 2],
                rgb_points[i + 3],
            )
        rgb = [0.0, 0.0, 0.0]
        for tick in ticks:
            t = tick["position"] / 100.0
            value = img_min + t * img_range
            linear_ctf.GetColor(value, rgb)
            tick["color"] = tick_contrast_color(rgb[0], rgb[1], rgb[2])
        self.color_ticks = ticks

    # --- Public API ---

    def set_data_array(self, variable_name, data_array_fn, scalar_mode="cell"):
        """Switch the coloring to a different data array at runtime.

        Reconfigures the mapper's scalar mode and color array, updates the
        data-array callback, recomputes the color range, and re-applies the
        current preset.

        Args:
            variable_name: Name of the new VTK data array to color by.
            data_array_fn: Callable returning the new VTK data array (or None).
            scalar_mode: ``"cell"`` (default), ``"point"``, or ``"default"``.
        """
        if not self._mapper:
            msg = "No mapper available on dataclass"
            raise ValueError(msg)

        self._get_data_array = data_array_fn
        self._mapper.SetScalarVisibility(1)
        if scalar_mode == "point":
            self._mapper.SetScalarModeToUsePointFieldData()
        elif scalar_mode == "cell":
            self._mapper.SetScalarModeToUseCellFieldData()
        if scalar_mode in ("point", "cell"):
            self._mapper.SelectColorArray(variable_name)
        self.update_color_range()
        self.update_color_preset(
            self.preset,
            self.invert,
            self.use_log_scale,
            self.discrete_log,
            self.n_discrete_colors,
            self.n_ticks,
        )
        return self

    def update_color_range(self):
        """Recompute the color range and re-apply the current preset.

        When override_range is False, the range is derived from the data
        array returned by data_array_fn.  When True, the existing manual
        range is kept and only rescaled onto the CTF.
        """
        if not self._mapper:
            msg = "No mapper available on dataclass"
            raise ValueError(msg)

        if self.override_range:
            skip_update = False
            if math.isnan(self.color_range[0]):
                skip_update = True
                self.color_value_min_valid = False

            if math.isnan(self.color_range[1]):
                skip_update = True
                self.color_value_max_valid = False

            if skip_update:
                return

            rescale_ctf(self._ctf, *self.color_range)
        else:
            data_array = self._get_data_array()
            if data_array:
                data_range = data_array.GetRange()
                self.color_range = data_range
                self.color_value_min = str(data_range[0])
                self.color_value_max = str(data_range[1])
                self.color_value_min_valid = True
                self.color_value_max_valid = True
                rescale_ctf(self._ctf, *data_range)

        self.update_color_preset(
            self.preset,
            self.invert,
            self.use_log_scale,
            self.discrete_log,
            self.n_discrete_colors,
            self.n_ticks,
        )

    @watch(
        "preset",
        "invert",
        "use_log_scale",
        "discrete_log",
        "n_discrete_colors",
        "n_ticks",
        eager=True,
    )
    def update_color_preset(
        self,
        name,
        invert,
        log_scale,
        discrete_log=False,
        n_discrete_colors=4,
        n_ticks=5,
    ):
        """Apply a color preset with the specified scale and discrete settings.

        Args:
            name: Preset name (must exist in PRESET_REGISTRY).
            invert: Whether to invert the transfer function.
            log_scale: Scale mode — ``"linear"``, ``"log"``, or ``"symlog"``.
            discrete_log: Enable discrete (stepped) color banding.
            n_discrete_colors: Number of color bands between ticks (linear)
                or per decade (log/symlog).
            n_ticks: Desired number of tick marks on the colorbar.
        """
        if not self._mapper:
            msg = "No mapper available on dataclass"
            raise ValueError(msg)

        self.preset = name

        # apply_preset resets range to [0,1], so always apply the linear
        # preset first, rescale to the current range, then apply transforms
        apply_linear(self._ctf, name, invert)
        rescale_ctf(self._ctf, *self.color_range)

        # Capture the linear colorbar image (always the same regardless of scale)
        self.effective_color_range = self._ctf.GetRange()
        self.lut_img_h = lut_to_img_h(self._ctf)
        self.lut_img_v = lut_to_img_v(self._ctf)

        # Save a copy of the linear control points for tick contrast sampling
        linear_rgb_points = get_rgb_points(self._ctf)

        # Compute linthresh (smallest positive non-zero value) from data
        # for log and symlog scales.
        linthresh = None
        if log_scale in ("log", "symlog"):
            arr = self._get_data_array()
            if arr is not None:
                linthresh = calculate_linthresh(vtk_to_numpy(arr))
            else:
                linthresh = 1.0

        n_sub = max(1, min(20, int(n_discrete_colors)))

        if log_scale == "linear" and discrete_log:
            vmin, vmax = self.color_range
            tick_vals = get_nice_ticks(vmin, vmax, n_ticks, scale="linear")
            result = apply_discrete_linear(
                self._ctf, linear_rgb_points, n_sub, tick_vals=tick_vals
            )
            if result[0] is not None:
                linear_rgb_points = result[0]
                self.lut_img_h = result[2]
                self.lut_img_v = result[3]
        elif log_scale == "log":
            if discrete_log:
                # Compute major ticks (powers of 10) for discrete band boundaries
                vmin, vmax = self.color_range
                log_major_ticks = get_nice_ticks(
                    vmin, vmax, n_ticks, scale="log", linthresh=linthresh
                )
                # Keep only powers of 10 as boundaries
                major_only = [
                    v
                    for v in log_major_ticks
                    if v > 0 and np.isclose(np.log10(v) % 1, 0, atol=1e-9)
                ]
                result = apply_discrete_log(
                    self._ctf,
                    linthresh,
                    linear_rgb_points,
                    n_sub,
                    tick_vals=major_only,
                )
                if result[0] is not None:
                    linear_rgb_points = result[0]
                    self.lut_img_h = result[2]
                    self.lut_img_v = result[3]
            else:
                result = apply_log(self._ctf, linthresh, linear_rgb_points)
                if result:
                    self.lut_img_h = result[0]
                    self.lut_img_v = result[1]
        elif log_scale == "symlog":
            if discrete_log:
                result = apply_discrete_symlog(
                    self._ctf, linthresh, linear_rgb_points, n_sub
                )
                if result[0] is not None:
                    linear_rgb_points = result[0]
                    self.lut_img_h = result[2]
                    self.lut_img_v = result[3]
            else:
                result = apply_symlog(self._ctf, linthresh, linear_rgb_points)
                if result:
                    self.lut_img_h = result[0]
                    self.lut_img_v = result[1]

        self._compute_ticks(
            linthresh=linthresh,
            linear_rgb_points=linear_rgb_points,
            n_ticks=n_ticks,
        )

        # For log, symlog (or any discrete mode), rebuild a separate CTF
        # so the mapper gets the correct points.
        if log_scale in ("symlog", "log") or (discrete_log and log_scale == "linear"):
            pts = get_rgb_points(self._ctf)
            render_ctf = vtkColorTransferFunction()
            for i in range(0, len(pts), 4):
                render_ctf.AddRGBPoint(pts[i], pts[i + 1], pts[i + 2], pts[i + 3])
            self._symlog_ctf = render_ctf  # prevent GC
            self._mapper.SetLookupTable(render_ctf)
        else:
            self._mapper.SetLookupTable(self._ctf)

        self._mapper.SetScalarRange(self.color_range)

        self.mapper_change += 1
