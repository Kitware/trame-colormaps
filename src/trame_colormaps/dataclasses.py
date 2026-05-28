"""Colormap configuration state model.

Self-contained state for a single colormap instance, including preset name,
scale mode, range, discrete settings, and derived display data (lut_img_h/v, ticks).

Can be used standalone or composed into a larger application config.
"""

import math

import numpy as np
from trame.app.dataclass import ServerOnly, StateDataModel, Sync, get_instance, watch
from vtkmodules.util.numpy_support import vtk_to_numpy
from vtkmodules.vtkRenderingCore import vtkColorTransferFunction

from trame_colormaps.core.presets import (
    COLOR_BLIND_SAFE,
    COLORBAR_CACHE,
    CYCLIC_PRESETS,
    DEFAULT_PRESETS,
    DIVERGING_PRESETS,
    MULTI_SEQUENTIAL_PRESETS,
    SEQUENTIAL_PRESETS,
    get_rgb_points,
    lut_to_img_h,
    lut_to_img_v,
    rescale_ctf,
    set_rgb_points,
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

_CATEGORY_SETS = {
    "sequential": SEQUENTIAL_PRESETS,
    "multi-sequential": MULTI_SEQUENTIAL_PRESETS,
    "diverging": DIVERGING_PRESETS,
    "cyclic": CYCLIC_PRESETS,
}

__all__ = ["ColormapConfig"]


class ColormapConfig(StateDataModel):
    """Reactive state model for a single colormap instance.

    Fields fall into three groups:

    **User-settable** — bound to UI controls, trigger reactive updates:

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

    **Derived** — computed internally, consumed by UI:

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
    - ``orientation``: Colorbar orientation (``"horizontal"`` or ``"vertical"``).
    - ``mapper_change``: Server-only counter incremented on each mapper update.
    """

    # --- User-settable (bound to UI, triggers reactive updates) ---
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
    diverging: bool = Sync(bool, False)
    epsilon: str = Sync(str, "0")
    abs_max: str = Sync(str, "")

    # --- Derived (computed internally, read by UI) ---
    color_value_min_valid: bool = Sync(bool, True)
    color_value_max_valid: bool = Sync(bool, True)
    epsilon_valid: bool = Sync(bool, True)
    abs_max_valid: bool = Sync(bool, True)
    color_range: list[float] = Sync(tuple[float, float], (0, 1))
    n_colors: int = Sync(int, 255)
    lut_img_h: str = Sync(str)
    lut_img_v: str = Sync(str)
    color_ticks: list = Sync(list, list)
    effective_color_range: list[float] = Sync(tuple[float, float], (0, 1))
    luts_normal: list = Sync(list, list)
    luts_inverted: list = Sync(list, list)

    # --- NaN color ---
    nan_color: list[float] = Sync(list, [0.0, 0.0, 0.0, 0.0])

    # --- UI widget state (control panel popup) ---
    menu: bool = Sync(bool, False)
    search: str | None = Sync(str)
    orientation: str = Sync(str, "horizontal")
    mapper_change: int = ServerOnly(int, 0)
    show_categories: bool = Sync(bool, False)
    selected_categories: str = Sync(str, "sequential")
    show_nan_menu: bool = Sync(bool, False)

    def __init__(self, *args, mapper=None, data_array_fn=None, **kwargs):
        # Create and own the CTF
        self._ctf = vtkColorTransferFunction()
        self._ctf.SetNanColorRGBA(0.0, 0.0, 0.0, 0.0)
        self._mapper = mapper
        self._get_data_array = data_array_fn

        if self._mapper:
            self._mapper.SetLookupTable(self._ctf)
            self._mapper.SetUseLookupTableScalarRange(True)

        # Saved state for restoring when leaving diverging mode
        self._saved_active_presets = None
        self._saved_log_scale = None
        self._saved_override_range = None

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

    @watch("diverging")
    def _on_diverging_change(self, diverging):
        """Enter or leave diverging mode.

        On enter: save current active_presets and use_log_scale, filter presets
        to diverging-only, force log scale away from 'log', enable override_range,
        and recompute the symmetric range centered at zero.

        On leave: restore saved presets and log scale.
        """
        if diverging:
            self._saved_active_presets = list(self.active_presets)
            self._saved_log_scale = self.use_log_scale
            self._saved_override_range = self.override_range
            # Filter active presets to diverging-only
            div_presets = [n for n in self.active_presets if n in DIVERGING_PRESETS]
            if not div_presets:
                # Fall back to all diverging presets from the full registry
                div_presets = sorted(DIVERGING_PRESETS)
            self.active_presets = div_presets
            # Force log scale to linear if it was 'log' (only linear/symlog allowed)
            if self.use_log_scale == "log":
                self.use_log_scale = "linear"
            # Switch to first diverging preset if current is not diverging
            if self.preset not in DIVERGING_PRESETS:
                self.preset = div_presets[0] if div_presets else self.preset
            # Enable override range, compute abs_max from data, apply symmetric range
            self.override_range = True
            self._compute_abs_max_from_data()
            self._apply_symmetric_range()
        else:
            # Restore presets from category selection
            self.selected_categories = "sequential"
            presets = _CATEGORY_SETS.get(self.selected_categories, set())
            self.active_presets = sorted(presets) if presets else sorted(DEFAULT_PRESETS)
            self._saved_active_presets = None
            if self._saved_log_scale is not None:
                self.use_log_scale = self._saved_log_scale
                self._saved_log_scale = None
            if self._saved_override_range is not None:
                self.override_range = self._saved_override_range
                self._saved_override_range = None
            # Recompute range from data so we leave the symmetric range
            self.update_color_range()

    @watch("selected_categories")
    def _on_categories_change(self, selected_categories):
        """Rebuild active_presets from the selected category.

        In diverging mode, active_presets is always diverging-only
        regardless of category selection.
        """
        if self.diverging:
            return
        presets = _CATEGORY_SETS.get(selected_categories, set())
        self.active_presets = sorted(presets) if presets else sorted(DEFAULT_PRESETS)

    @watch("epsilon")
    def _on_epsilon_change(self, epsilon):
        """Validate epsilon string and re-apply preset if in diverging mode.

        Epsilon modifies the CTF (not the range) by injecting a dead zone
        of center color around zero.
        """
        try:
            val = float(epsilon)
            self.epsilon_valid = val >= 0 and not math.isnan(val)
        except (ValueError, TypeError):
            self.epsilon_valid = False

        if self.diverging and self.epsilon_valid:
            self.update_color_preset(
                self.preset,
                self.invert,
                self.use_log_scale,
                self.discrete_log,
                self.n_discrete_colors,
                self.n_ticks,
            )

    @watch("abs_max")
    def _on_abs_max_change(self, abs_max):
        """Validate abs_max and recompute symmetric range if diverging."""
        try:
            val = float(abs_max)
            self.abs_max_valid = val > 0 and not math.isnan(val)
        except (ValueError, TypeError):
            self.abs_max_valid = False

        if self.diverging and self.abs_max_valid:
            self._apply_symmetric_range()

    def _compute_abs_max_from_data(self):
        """Populate abs_max field from data array range."""
        if not self._get_data_array:
            return
        data_array = self._get_data_array()
        if not data_array:
            return
        data_range = data_array.GetRange()
        abs_max_val = max(abs(data_range[0]), abs(data_range[1]))
        self.abs_max = str(abs_max_val)

    def _apply_symmetric_range(self):
        """Apply the symmetric range centered at zero.

        Range is [-abs_max, +abs_max]. Epsilon does NOT expand the range;
        instead it creates a dead zone in the CTF around zero where the
        center color is held constant.
        """
        try:
            abs_max_val = float(self.abs_max)
        except (ValueError, TypeError):
            return

        if abs_max_val <= 0:
            return

        self.color_value_min = str(-abs_max_val)
        self.color_value_max = str(abs_max_val)
        self.color_value_min_valid = True
        self.color_value_max_valid = True
        self.color_range = (-abs_max_val, abs_max_val)

    def _inject_epsilon_band(self):
        """Insert an epsilon dead zone into the CTF around zero.

        Redistributes control points so that:
        - Points in [-abs_max, 0) are linearly remapped into [-abs_max, -eps]
        - Points in (0, +abs_max] are linearly remapped into [+eps, +abs_max]
        - The band [-eps, +eps] is flat center color (sampled at x=0)

        This compresses the colormap into the outer regions and holds the
        center color constant across the tolerance band.
        """
        try:
            eps = float(self.epsilon) if self.epsilon_valid else 0.0
        except (ValueError, TypeError):
            eps = 0.0
        eps = max(0.0, eps)

        if eps <= 0:
            return

        vmin, vmax = self.color_range
        if vmax <= 0 or vmin >= 0:
            return

        # Sample center color at x=0 before redistribution
        rgb = [0.0, 0.0, 0.0]
        self._ctf.GetColor(0.0, rgb)
        cr, cg, cb = rgb[0], rgb[1], rgb[2]

        # Get current control points
        pts = get_rgb_points(self._ctf)
        n = len(pts) // 4

        # Separate into left (x < 0), center (x == 0), and right (x > 0)
        left_pts = []  # will be remapped into [vmin, -eps]
        right_pts = []  # will be remapped into [+eps, vmax]
        for i in range(n):
            x = pts[i * 4]
            r, g, b = pts[i * 4 + 1], pts[i * 4 + 2], pts[i * 4 + 3]
            if x < 0:
                left_pts.append((x, r, g, b))
            elif x > 0:
                right_pts.append((x, r, g, b))
            # x == 0 control point is replaced by the band

        # Remap left points: [vmin, 0) → [vmin, -eps]
        new_pts = []
        if left_pts:
            old_min = vmin
            old_max = 0.0
            new_min = vmin
            new_max = -eps
            old_range = old_max - old_min
            new_range = new_max - new_min
            for x, r, g, b in left_pts:
                if old_range != 0:
                    t = (x - old_min) / old_range
                    nx = new_min + t * new_range
                else:
                    nx = new_min
                new_pts.extend([nx, r, g, b])

        # Insert dead zone band
        new_pts.extend([-eps, cr, cg, cb])
        new_pts.extend([0.0, cr, cg, cb])
        new_pts.extend([eps, cr, cg, cb])

        # Remap right points: (0, vmax] → [+eps, vmax]
        if right_pts:
            old_min = 0.0
            old_max = vmax
            new_min = eps
            new_max = vmax
            old_range = old_max - old_min
            new_range = new_max - new_min
            for x, r, g, b in right_pts:
                if old_range != 0:
                    t = (x - old_min) / old_range
                    nx = new_min + t * new_range
                else:
                    nx = new_max
                new_pts.extend([nx, r, g, b])

        set_rgb_points(self._ctf, new_pts)

    @watch("override_range", "color_range", eager=True)
    def _on_range_change(self, *_):
        """Reactive handler for override_range or color_range changes."""
        self.update_color_range()

    @watch("active_presets", eager=True)
    def _build_lut_lists(self, active_presets):
        """Rebuild the sorted preset picker lists from active_presets.

        Filters COLORBAR_CACHE by the given preset names and populates
        ``self.luts_normal`` and ``self.luts_inverted``.

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
                if self.diverging and vmin < 0 < vmax:
                    # Symmetric ticks: compute for positive half, mirror
                    half_n = max(2, n_ticks // 2 + 1)
                    pos_ticks = get_nice_ticks(0, vmax, half_n, scale="linear")
                    sym = set()
                    for v in pos_ticks:
                        sym.add(float(v))
                        sym.add(float(-v))
                    sym.add(0.0)
                    tick_vals = np.array(sorted(sym))
                    # Filter to range
                    tick_vals = tick_vals[
                        (tick_vals > vmin + data_range * 0.01)
                        & (tick_vals < vmax - data_range * 0.01)
                    ]
                else:
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
                if self.diverging and vmin < 0 < vmax:
                    # Symmetric ticks: compute for positive half, mirror
                    half_n = max(2, n_ticks // 2 + 1)
                    pos_ticks = get_nice_ticks(
                        0,
                        vmax,
                        half_n,
                        scale=self.use_log_scale,
                        linthresh=linthresh,
                    )
                    sym = set()
                    for v in pos_ticks:
                        sym.add(float(v))
                        sym.add(float(-v))
                    sym.add(0.0)
                    tick_vals = np.array(sorted(sym))
                    tick_vals = tick_vals[
                        (tick_vals > vmin + data_range * 0.01)
                        & (tick_vals < vmax - data_range * 0.01)
                    ]
                else:
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
                    ticks.append({"position": round(pos, 2), "label": format_log_tick(val)})

        # Sample colors from the *linear* CTF so tick contrast matches the
        # displayed colorbar image, not the log/symlog-remapped rendering CTF.
        rgb_points = linear_rgb_points if linear_rgb_points else get_rgb_points(self._ctf)
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
            name: Preset name (must exist in COLORBAR_CACHE).
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

        # In diverging mode, inject an epsilon dead zone around zero.
        # For symlog, the dead zone is handled inside apply_symlog /
        # apply_discrete_symlog so that it aligns with the symlog transform.
        if self.diverging and log_scale != "symlog":
            self._inject_epsilon_band()

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
            # In diverging mode, inject epsilon boundaries so the dead
            # zone is always preserved as its own discrete region.
            if self.diverging and self.epsilon_valid:
                try:
                    eps = float(self.epsilon)
                except (ValueError, TypeError):
                    eps = 0.0
                if eps > 0:
                    eps_bounds = [-eps, eps]
                    merged = sorted(set(list(tick_vals) + eps_bounds))
                    tick_vals = np.array(merged)
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
            # Compute epsilon for diverging symlog dead zone
            symlog_eps = 0.0
            if self.diverging and self.epsilon_valid:
                try:
                    symlog_eps = max(0.0, float(self.epsilon))
                except (ValueError, TypeError):
                    symlog_eps = 0.0
            if discrete_log:
                result = apply_discrete_symlog(
                    self._ctf,
                    linthresh,
                    linear_rgb_points,
                    n_sub,
                    epsilon=symlog_eps,
                )
                if result[0] is not None:
                    linear_rgb_points = result[0]
                    self.lut_img_h = result[2]
                    self.lut_img_v = result[3]
            else:
                result = apply_symlog(
                    self._ctf,
                    linthresh,
                    linear_rgb_points,
                    epsilon=symlog_eps,
                )
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
        self._apply_nan_color()

        self.mapper_change += 1

    @watch("nan_color", eager=True)
    def _on_nan_color_change(self, nan_color):
        """Apply NaN color to the active CTF(s) whenever it changes."""
        self._apply_nan_color()
        self.mapper_change += 1

    def _apply_nan_color(self):
        """Set NaN color (RGBA) on all active CTFs."""
        c = self.nan_color
        if not c or len(c) < 4:
            c = [0.0, 0.0, 0.0, 0.0]
        r, g, b, a = float(c[0]), float(c[1]), float(c[2]), float(c[3])
        self._ctf.SetNanColorRGBA(r, g, b, a)
        if hasattr(self, "_symlog_ctf") and self._symlog_ctf:
            self._symlog_ctf.SetNanColorRGBA(r, g, b, a)
