"""Colormap controller with reactive state management.

Self-contained controller that manages a single colormap's CTF, config state,
and rendering. Designed to be instantiated per-view and wired to a VTK mapper.
"""

import math

from vtkmodules.util.numpy_support import vtk_to_numpy
from vtkmodules.vtkRenderingCore import vtkColorTransferFunction

from trame_colormaps.core.presets import (
    COLOR_BLIND_SAFE,
    COLORBAR_CACHE,
    get_rgb_points,
    lut_to_img_h,
    lut_to_img_v,
    rescale_ctf,
)
from trame_colormaps.core.ticks import (
    compute_color_ticks,
    format_tick,
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
from trame_colormaps.state import ColormapConfig


class ColormapController:
    """Self-contained colormap manager for one variable view.

    Creates and owns a vtkColorTransferFunction and wires it to the mapper.

    Args:
        server: Trame server instance
        variable_name: Name of the data array to color by
        mapper: VTK mapper whose LookupTable and scalar mode are configured
        data_array_fn: Callable returning the current VTK data array (or None)
        render_fn: Callable to trigger a render after changes
        config: Optional existing config object with colormap fields.
                If None, a new ColormapConfig is created.
        scalar_mode: How the mapper finds the scalar array.  One of
            ``"cell"`` (default) or ``"point"``.
    """

    def __init__(
        self,
        server,
        variable_name,
        mapper,
        data_array_fn,
        render_fn,
        config=None,
        scalar_mode="cell",
    ):
        self.config = config if config is not None else ColormapConfig(server)

        # Create and own the CTF
        self._ctf = vtkColorTransferFunction()

        # Wire the mapper to use this CTF for coloring
        mapper.SetScalarVisibility(1)
        if scalar_mode == "point":
            mapper.SetScalarModeToUsePointFieldData()
            mapper.SelectColorArray(variable_name)
        elif scalar_mode == "cell":
            mapper.SetScalarModeToUseCellFieldData()
            mapper.SelectColorArray(variable_name)
        # else: "default" — use the active scalars as-is
        mapper.SetColorModeToMapScalars()
        mapper.InterpolateScalarsBeforeMappingOn()
        mapper.SetLookupTable(self._ctf)

        self._mapper = mapper
        self._get_data_array = data_array_fn
        self._render = render_fn
        # Keeps a reference to the separate render CTF used for symlog/discrete
        # modes so it is not garbage-collected while the mapper holds it.
        self._symlog_ctf = None

        # Reactive watchers
        self.config.watch(
            ["color_value_min", "color_value_max"],
            self._on_range_str_change,
        )
        self.config.watch(
            ["override_range", "color_range"],
            self._on_range_change,
            eager=True,
        )
        self.config.watch(
            [
                "preset",
                "invert",
                "use_log_scale",
                "discrete_log",
                "n_discrete_colors",
                "n_intervals",
                "n_ticks",
            ],
            self.update_color_preset,
            eager=True,
        )
        self.config.watch(
            ["active_presets"],
            self._build_lut_lists,
            eager=True,
        )

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
        self._get_data_array = data_array_fn
        self._mapper.SetScalarVisibility(1)
        if scalar_mode == "point":
            self._mapper.SetScalarModeToUsePointFieldData()
        elif scalar_mode == "cell":
            self._mapper.SetScalarModeToUseCellFieldData()
        if scalar_mode in ("point", "cell"):
            self._mapper.SelectColorArray(variable_name)
        self.update_color_range()
        self.update_color_preset()

    def update_color_range(self):
        """Recompute the color range and re-apply the current preset.

        When override_range is False, the range is derived from the data
        array returned by data_array_fn.  When True, the existing manual
        range is kept and only rescaled onto the CTF.
        """
        if self.config.override_range:
            skip_update = False
            if math.isnan(self.config.color_range[0]):
                skip_update = True
                self.config.color_value_min_valid = False

            if math.isnan(self.config.color_range[1]):
                skip_update = True
                self.config.color_value_max_valid = False

            if skip_update:
                return

            rescale_ctf(self._ctf, *self.config.color_range)
        else:
            data_array = self._get_data_array()
            if data_array:
                data_range = data_array.GetRange()
                self.config.color_range = data_range
                self.config.color_value_min = str(data_range[0])
                self.config.color_value_max = str(data_range[1])
                self.config.color_value_min_valid = True
                self.config.color_value_max_valid = True
                rescale_ctf(self._ctf, *data_range)

        self.update_color_preset(
            self.config.preset,
            self.config.invert,
            self.config.use_log_scale,
            self.config.discrete_log,
            self.config.n_discrete_colors,
            self.config.n_intervals,
            self.config.n_ticks,
        )

    def update_color_preset(
        self,
        name,
        invert,
        log_scale,
        discrete_log=False,
        n_discrete_colors=4,
        n_intervals=4,
        n_ticks=5,
    ):
        """Apply a color preset with the specified scale and discrete settings.

        Args:
            name: Preset name (must exist in PRESET_REGISTRY).
            invert: Whether to invert the transfer function.
            log_scale: Scale mode — ``"linear"``, ``"log"``, or ``"symlog"``.
            discrete_log: Enable discrete (stepped) color banding.
            n_discrete_colors: Number of sub-bands per interval (1–20).
            n_intervals: Number of equal intervals for discrete linear mode.
            n_ticks: Desired number of tick marks on the colorbar.
        """
        self.config.preset = name

        # apply_preset resets range to [0,1], so always apply the linear
        # preset first, rescale to the current range, then apply transforms
        apply_linear(self._ctf, name, invert)
        rescale_ctf(self._ctf, *self.config.color_range)

        # Capture the linear colorbar image (always the same regardless of scale)
        self.config.effective_color_range = self._ctf.GetRange()
        self.config.lut_img_h = lut_to_img_h(self._ctf)
        self.config.lut_img_v = lut_to_img_v(self._ctf)

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
            result = apply_discrete_linear(
                self._ctf, linear_rgb_points, n_sub, n_intervals=n_intervals
            )
            if result[0] is not None:
                linear_rgb_points = result[0]
                self.config.lut_img_h = result[2]
                self.config.lut_img_v = result[3]
        elif log_scale == "log":
            if discrete_log:
                result = apply_discrete_log(
                    self._ctf, linthresh, linear_rgb_points, n_sub
                )
                if result[0] is not None:
                    linear_rgb_points = result[0]
                    self.config.lut_img_h = result[2]
                    self.config.lut_img_v = result[3]
            else:
                apply_log(self._ctf, linthresh)
                self.config.lut_img_h = lut_to_img_h(self._ctf)
                self.config.lut_img_v = lut_to_img_v(self._ctf)
        elif log_scale == "symlog":
            if discrete_log:
                result = apply_discrete_symlog(
                    self._ctf, linthresh, linear_rgb_points, n_sub
                )
                if result[0] is not None:
                    linear_rgb_points = result[0]
                    self.config.lut_img_h = result[2]
                    self.config.lut_img_v = result[3]
            else:
                result = apply_symlog(self._ctf, linthresh, linear_rgb_points)
                if result:
                    self.config.lut_img_h = result[0]
                    self.config.lut_img_v = result[1]

        self._compute_ticks(
            linthresh=linthresh,
            linear_rgb_points=linear_rgb_points,
            n_intervals=n_intervals,
            n_ticks=n_ticks,
        )

        # For symlog (or any discrete mode), rebuild a separate CTF
        # so the mapper gets the correct points.
        if log_scale == "symlog" or (discrete_log and log_scale in ("log", "linear")):
            pts = get_rgb_points(self._ctf)
            render_ctf = vtkColorTransferFunction()
            for i in range(0, len(pts), 4):
                render_ctf.AddRGBPoint(pts[i], pts[i + 1], pts[i + 2], pts[i + 3])
            self._symlog_ctf = render_ctf  # prevent GC
            self._mapper.SetLookupTable(render_ctf)
        else:
            self._mapper.SetLookupTable(self._ctf)

        self._mapper.SetScalarRange(self.config.color_range)
        self._mapper.Modified()

        self._render()

    # --- Private reactive handlers ---

    def _on_range_str_change(self, color_value_min, color_value_max):
        """Validate min/max strings and update color_range if both are valid."""
        try:
            min_value = float(color_value_min)
            self.config.color_value_min_valid = not math.isnan(min_value)
        except ValueError:
            self.config.color_value_min_valid = False

        try:
            max_value = float(color_value_max)
            self.config.color_value_max_valid = not math.isnan(max_value)
        except ValueError:
            self.config.color_value_max_valid = False

        if self.config.color_value_min_valid and self.config.color_value_max_valid:
            self.config.color_range = (min_value, max_value)

    def _on_range_change(self, *_):
        """Reactive handler for override_range or color_range changes."""
        self.update_color_range()

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
        self.config.luts_normal = luts_normal
        self.config.luts_inverted = luts_inverted

    def _compute_ticks(
        self, linthresh=None, linear_rgb_points=None, n_intervals=4, n_ticks=5
    ):
        """Compute tick positions, labels, and contrast colors for the colorbar.

        Args:
            linthresh: Linear threshold for log/symlog scale (None for linear).
            linear_rgb_points: RGB control points from the linear CTF, used to
                sample contrast colors. Falls back to current CTF points.
            n_intervals: Number of equal intervals for linear tick placement.
            n_ticks: Desired number of tick marks for log/symlog scales.
        """
        vmin, vmax = self.config.color_range

        # Ticks are computed the same regardless of discrete mode.
        if self.config.use_log_scale == "linear":
            data_range = vmax - vmin
            ticks = []
            if data_range > 0:
                for i in range(1, n_intervals):
                    val = vmin + data_range * i / n_intervals
                    pos = i / n_intervals * 100
                    ticks.append({"position": round(pos, 2), "label": format_tick(val)})
        else:
            ticks = compute_color_ticks(
                vmin,
                vmax,
                scale=self.config.use_log_scale,
                n=n_ticks,
                linthresh=linthresh,
            )

        # Sample colors from the *linear* CTF so tick contrast matches the
        # displayed colorbar image, not the log/symlog-remapped rendering CTF.
        rgb_points = (
            linear_rgb_points if linear_rgb_points else get_rgb_points(self._ctf)
        )
        if len(rgb_points) < 4:
            self.config.color_ticks = []
            return
        img_min = rgb_points[0]
        img_max = rgb_points[-4]
        img_range = img_max - img_min
        if img_range == 0:
            self.config.color_ticks = []
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
        self.config.color_ticks = ticks
