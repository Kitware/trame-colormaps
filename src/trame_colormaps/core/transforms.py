"""LUT transform operations for color transfer functions.

Provides functions that operate on vtkColorTransferFunction objects to apply:
- Linear presets (with optional inversion)
- Discrete linear banding
- Log scale mapping
- Discrete log banding
- Symlog (symmetric log) mapping
- Discrete symlog banding

These functions are designed to be called by ColormapConfig but
have no framework dependencies beyond VTK and numpy.
"""

import numpy as np
from vtkmodules.vtkRenderingCore import vtkColorTransferFunction

from trame_colormaps.core.presets import (
    apply_preset,
    get_rgb_points,
    invert_ctf,
    lut_to_img_h,
    lut_to_img_v,
    set_rgb_points,
)


def calculate_linthresh(data):
    """Calculate the linear threshold for symlog scaling.

    Excludes true zeros (values within ±tiny of the data dtype),
    then returns min(abs(valid)).

    Operates on the original array without copies.

    Args:
        data: numpy array of data values

    Returns:
        linthresh value (float), floored at dtype tiny to avoid zero
    """
    threshold = np.finfo(data.dtype).tiny

    # Find min |x| > threshold without allocating a copy.
    # Using where= runs as a tight vectorized C loop, roughly 2-3 orders
    # of magnitude faster than a Python for loop.
    min_pos = np.nanmin(data, where=data > threshold, initial=np.inf)
    # For negatives: max(data) where data < -threshold gives closest to zero
    max_neg = np.nanmax(data, where=data < -threshold, initial=-np.inf)
    min_abs = min(min_pos, -max_neg)

    if min_abs == np.inf:
        linthresh = 1.0
    else:
        linthresh = max(float(min_abs), float(np.finfo(data.dtype).tiny))

    return linthresh


def apply_linear(ctf, preset_name, invert=False):
    """Apply a color preset with linear scale.

    Loads the named preset into the CTF and optionally inverts it.

    Args:
        ctf: vtkColorTransferFunction.
        preset_name: Name of the color preset.
        invert: Whether to invert the transfer function.
    """
    apply_preset(ctf, preset_name)
    if invert:
        invert_ctf(ctf)


def apply_discrete_linear(ctf, linear_rgb_points, n_sub=1, tick_vals=None):
    """Build a discrete (stepped) linear LUT aligned with tick marks.

    Boundaries are [x_min, tick1, tick2, ..., x_max].  Each region
    between adjacent boundaries is split into *n_sub* equal sub-bands,
    each with a flat color sampled from the continuous linear LUT at
    the sub-band midpoint.

    Args:
        ctf: vtkColorTransferFunction.
        linear_rgb_points: RGB control points from the linear LUT.
        n_sub: Number of discrete color bands per region between ticks.
        tick_vals: Sorted array of tick values (interior boundaries).
            If None, falls back to a single region [x_min, x_max].

    Returns:
        Tuple of (display_rgb_points, discrete_tick_data, lut_img_h, lut_img_v)
        or (None, None, None, None) if the data range is zero.
    """
    x_min, x_max = ctf.GetRange()
    data_range = x_max - x_min
    if data_range == 0:
        return None, None, None, None

    # Build boundaries from tick values: [x_min, tick1, ..., x_max]
    boundaries = [x_min]
    if tick_vals is not None and len(tick_vals) > 0:
        for v in tick_vals:
            if x_min < v < x_max:
                boundaries.append(float(v))
    boundaries.append(x_max)

    if len(boundaries) < 2:
        return None, None, None, None

    # Build a temporary linear CTF from the saved linear RGB points
    linear_ctf = vtkColorTransferFunction()
    for i in range(0, len(linear_rgb_points), 4):
        linear_ctf.AddRGBPoint(
            linear_rgb_points[i],
            linear_rgb_points[i + 1],
            linear_rgb_points[i + 2],
            linear_rgb_points[i + 3],
        )

    rgb = [0.0, 0.0, 0.0]
    eps = data_range * 1e-9
    display_rgb_points = []
    render_rgb_points = []
    band_idx = 0
    total_bands = (len(boundaries) - 1) * n_sub
    for i in range(len(boundaries) - 1):
        lo = boundaries[i]
        hi = boundaries[i + 1]
        for j in range(n_sub):
            # Sub-band edges in linear space
            sub_lo = lo + (hi - lo) * j / n_sub
            sub_hi = lo + (hi - lo) * (j + 1) / n_sub
            sub_mid = (sub_lo + sub_hi) / 2.0
            linear_ctf.GetColor(sub_mid, rgb)
            r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])

            is_first = band_idx == 0
            is_last = band_idx == total_bands - 1

            if is_first:
                display_rgb_points.extend([sub_lo, r, g, b])
                render_rgb_points.extend([sub_lo, r, g, b])
            else:
                display_rgb_points.extend([sub_lo + eps, r, g, b])
                render_rgb_points.extend([sub_lo + eps, r, g, b])

            if is_last:
                display_rgb_points.extend([sub_hi, r, g, b])
                render_rgb_points.extend([sub_hi, r, g, b])
            else:
                display_rgb_points.extend([sub_hi - eps, r, g, b])
                render_rgb_points.extend([sub_hi - eps, r, g, b])

            band_idx += 1

    # Generate the discrete banded colorbar image
    set_rgb_points(ctf, display_rgb_points)
    lut_img = lut_to_img_h(ctf)
    lut_img_v = lut_to_img_v(ctf)

    # Set rendering points on the CTF
    set_rgb_points(ctf, render_rgb_points)

    return display_rgb_points, None, lut_img, lut_img_v


def apply_log(ctf, linthresh, linear_rgb_points=None, n_samples=256):
    """Build a log CTF with two regions.

    [x_min, linthresh): flat color — clamped to the color at linthresh.
    [linthresh, x_max]: log-mapped colors sampled from the linear colorbar.

    Args:
        ctf: vtkColorTransferFunction.
        linthresh: Floor for log mapping. Values below get clamped color.
        linear_rgb_points: RGB control points from the linear LUT.
        n_samples: Number of uniform samples in the log region.

    Returns:
        Tuple of (lut_img_h, lut_img_v) base64 PNG strings, or None if
        the range is zero/invalid.
    """
    x_min, x_max = ctf.GetRange()
    data_range = x_max - x_min
    if data_range == 0:
        return None
    if x_max <= linthresh:
        return None

    # Build a standalone linear CTF for safe color sampling
    linear_ctf = vtkColorTransferFunction()
    if linear_rgb_points:
        src = linear_rgb_points
    else:
        src = get_rgb_points(ctf)
    for i in range(0, len(src), 4):
        linear_ctf.AddRGBPoint(src[i], src[i + 1], src[i + 2], src[i + 3])

    # Symlog-style transform (same as tick positioning)
    def _sl(v):
        return np.sign(v) * np.log10(1.0 + np.abs(v) / linthresh)

    sl_min = _sl(x_min)
    sl_max = _sl(x_max)
    sl_range = sl_max - sl_min
    if sl_range == 0:
        return None

    rgb = [0.0, 0.0, 0.0]
    new_rgb_points = []
    display_rgb_points = []

    # Sample the color at linthresh — this is the clamped color
    lt_disp_frac = (_sl(linthresh) - sl_min) / sl_range
    x_lt_lookup = x_min + lt_disp_frac * data_range
    linear_ctf.GetColor(x_lt_lookup, rgb)
    clamp_r, clamp_g, clamp_b = float(rgb[0]), float(rgb[1]), float(rgb[2])

    # --- Region 1: [x_min, linthresh) — flat clamped color ---
    if x_min < linthresh:
        # Two points to create a flat band up to linthresh display position
        new_rgb_points.extend([float(x_min), clamp_r, clamp_g, clamp_b])
        display_rgb_points.extend([float(x_min), clamp_r, clamp_g, clamp_b])
        d_lt = x_min + lt_disp_frac * data_range
        new_rgb_points.extend([float(linthresh) - data_range * 1e-9, clamp_r, clamp_g, clamp_b])
        display_rgb_points.extend([d_lt - data_range * 1e-9, clamp_r, clamp_g, clamp_b])

    # --- Region 2: [linthresh, x_max] — log-mapped ---
    log_min = np.log10(linthresh)
    log_max = np.log10(x_max)
    log_range = log_max - log_min
    if log_range <= 0:
        return None

    for i in range(n_samples):
        t = i / (n_samples - 1) if n_samples > 1 else 0.0
        lg = log_min + t * log_range
        v = 10.0**lg
        v = max(linthresh, min(x_max, v))
        # Sample color from linear colorbar at the symlog display position
        disp_frac = (_sl(v) - sl_min) / sl_range
        x_lookup = x_min + disp_frac * data_range
        linear_ctf.GetColor(x_lookup, rgb)
        r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])
        new_rgb_points.extend([float(v), r, g, b])
        # Display position uses symlog transform to match tick positioning
        d_pos = x_min + disp_frac * data_range
        display_rgb_points.extend([float(d_pos), r, g, b])

    # Generate colorbar image from display points
    set_rgb_points(ctf, display_rgb_points)
    lut_img = lut_to_img_h(ctf)
    lut_img_v = lut_to_img_v(ctf)

    # Store rendering points on the CTF
    set_rgb_points(ctf, new_rgb_points)

    return lut_img, lut_img_v


def apply_discrete_log(ctf, linthresh, linear_rgb_points, n_sub=1, tick_vals=None):
    """Build a discrete (stepped) log-scale LUT.

    Below linthresh: one flat band clamped to the color at linthresh.
    Above linthresh: decade bands from *tick_vals* (powers of 10), each
    split into *n_sub* equal sub-bands with a flat color sampled from
    the linear LUT.  Display positions use the symlog-style transform
    so bands align exactly with tick marks.

    Args:
        ctf: vtkColorTransferFunction.
        linthresh: Linear threshold for the log floor.
        linear_rgb_points: RGB control points from the linear LUT.
        n_sub: Number of sub-bands per decade.
        tick_vals: Major tick values (powers of 10) to use as boundaries.
            If None, decade boundaries are auto-computed.

    Returns:
        Tuple of (display_rgb_points, discrete_tick_data, lut_img_h,
        lut_img_v) or (None, None, None, None) if the range is invalid.
    """
    x_min, x_max = ctf.GetRange()
    if x_max <= x_min:
        return None, None, None, None
    lt = linthresh if linthresh is not None else 1.0

    # Symlog-style transform (same as tick positioning)
    def _sl(v):
        return np.sign(v) * np.log10(1.0 + np.abs(v) / lt)

    sl_min = _sl(x_min)
    sl_max = _sl(x_max)
    sl_range = sl_max - sl_min
    if sl_range == 0:
        return None, None, None, None

    # Build decade boundaries: only above linthresh gets discrete bands.
    # Below linthresh is one flat clamped band at the color of linthresh.
    if tick_vals is not None and len(tick_vals) > 0:
        interior = [v for v in tick_vals if lt < v < x_max and v != 0]
    else:
        # Fallback: auto-compute decade boundaries
        lo_b = max(lt, 1e-30)
        e_lo_b = int(np.floor(np.log10(lo_b)))
        e_hi_b = int(np.floor(np.log10(max(abs(x_max), lo_b))))
        interior = []
        for e in range(e_lo_b, e_hi_b + 1):
            val = 10.0**e
            if lt < val < x_max:
                interior.append(val)
    # Decade boundaries: [linthresh, ..., x_max]
    decade_boundaries = sorted(set([lt] + interior + [x_max]))

    if len(decade_boundaries) < 2:
        return None, None, None, None

    # Store boundary tick data for external use
    discrete_tick_data = []
    for bv in decade_boundaries[1:-1]:
        pct = (_sl(bv) - sl_min) / sl_range * 100
        discrete_tick_data.append({"val": bv, "pos": float(pct)})

    # Build a continuous linear CTF to sample colours from
    linear_ctf = vtkColorTransferFunction()
    for i in range(0, len(linear_rgb_points), 4):
        linear_ctf.AddRGBPoint(
            linear_rgb_points[i],
            linear_rgb_points[i + 1],
            linear_rgb_points[i + 2],
            linear_rgb_points[i + 3],
        )

    data_range = x_max - x_min
    rgb = [0.0, 0.0, 0.0]
    eps_data = data_range * 1e-9
    eps_disp = data_range * 1e-9
    display_rgb_points = []
    render_rgb_points = []

    # --- Flat clamped band: [x_min, linthresh] at color of linthresh ---
    # Sample the color at linthresh's display position
    lt_disp = (_sl(lt) - sl_min) / sl_range
    x_lt_lookup = x_min + lt_disp * data_range
    linear_ctf.GetColor(x_lt_lookup, rgb)
    r_lt, g_lt, b_lt = float(rgb[0]), float(rgb[1]), float(rgb[2])

    # Flat band from x_min to linthresh display position
    d_lt = x_min + lt_disp * data_range
    display_rgb_points.extend([float(x_min), r_lt, g_lt, b_lt])
    display_rgb_points.extend([d_lt - eps_disp, r_lt, g_lt, b_lt])
    render_rgb_points.extend([float(x_min), r_lt, g_lt, b_lt])
    render_rgb_points.extend([float(lt) - eps_data, r_lt, g_lt, b_lt])

    # --- Discrete decade bands: [linthresh, ..., x_max] ---
    band_idx = 0
    total_bands = (len(decade_boundaries) - 1) * n_sub

    for i in range(len(decade_boundaries) - 1):
        b_lo = decade_boundaries[i]
        b_hi = decade_boundaries[i + 1]
        sl_lo = _sl(b_lo)
        sl_hi = _sl(b_hi)

        for j in range(n_sub):
            # Sub-band edges in symlog space
            t0 = j / n_sub
            t1 = (j + 1) / n_sub
            sub_sl_lo = sl_lo + (sl_hi - sl_lo) * t0
            sub_sl_hi = sl_lo + (sl_hi - sl_lo) * t1
            sub_sl_mid = (sub_sl_lo + sub_sl_hi) / 2.0

            # Display positions as fraction of colorbar
            disp_lo = (sub_sl_lo - sl_min) / sl_range
            disp_hi = (sub_sl_hi - sl_min) / sl_range
            disp_mid = (sub_sl_mid - sl_min) / sl_range

            # Sample colour from linear CTF at display midpoint
            x_lookup = x_min + disp_mid * data_range
            linear_ctf.GetColor(x_lookup, rgb)
            r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])

            # Display-space positions
            d_lo = x_min + disp_lo * data_range
            d_hi = x_min + disp_hi * data_range

            # Data-space positions for rendering
            v_lo = b_lo + (b_hi - b_lo) * t0
            v_hi = b_lo + (b_hi - b_lo) * t1

            # First discrete band starts right after the clamped band
            display_rgb_points.extend([d_lo + eps_disp, r, g, b])
            render_rgb_points.extend([float(v_lo) + eps_data, r, g, b])

            is_last = band_idx == total_bands - 1
            if is_last:
                display_rgb_points.extend([d_hi, r, g, b])
                render_rgb_points.extend([float(v_hi), r, g, b])
            else:
                display_rgb_points.extend([d_hi - eps_disp, r, g, b])
                render_rgb_points.extend([float(v_hi) - eps_data, r, g, b])

            band_idx += 1

    # Generate the discrete banded colorbar image
    set_rgb_points(ctf, display_rgb_points)
    lut_img = lut_to_img_h(ctf)
    lut_img_v = lut_to_img_v(ctf)

    # Set rendering points on the CTF
    set_rgb_points(ctf, render_rgb_points)

    return display_rgb_points, discrete_tick_data, lut_img, lut_img_v


def _remap_with_dead_zone(pts, vmin, vmax, center, neg_eps, pos_eps, cr, cg, cb):
    """Compress control points outward from a dead zone.

    Points in ``[vmin, center)`` are linearly remapped into ``[vmin, neg_eps]``.
    Points in ``(center, vmax]`` are linearly remapped into ``[pos_eps, vmax]``.
    The band ``[neg_eps, center, pos_eps]`` is filled with the center color
    ``(cr, cg, cb)``.

    All original colors are retained — they are squeezed outward from
    the dead zone rather than discarded.

    Args:
        pts: Flat list ``[x, r, g, b, ...]`` of control points.
        vmin: Minimum x value of the range.
        vmax: Maximum x value of the range.
        center: The x value around which the dead zone is centered.
        neg_eps: Negative boundary of the dead zone.
        pos_eps: Positive boundary of the dead zone.
        cr, cg, cb: Center color (flat band fill).

    Returns a new flat list ``[x, r, g, b, ...]``.
    """
    n = len(pts) // 4
    left_pts = []
    right_pts = []
    for i in range(n):
        x = pts[i * 4]
        r, g, b = pts[i * 4 + 1], pts[i * 4 + 2], pts[i * 4 + 3]
        if x < center:
            left_pts.append((x, r, g, b))
        elif x > center:
            right_pts.append((x, r, g, b))

    new_pts = []
    # Remap left: [vmin, center) → [vmin, neg_eps]
    if left_pts:
        old_range = center - vmin
        new_range = neg_eps - vmin
        for x, r, g, b in left_pts:
            if old_range != 0:
                t = (x - vmin) / old_range
                nx = vmin + t * new_range
            else:
                nx = vmin
            new_pts.extend([nx, r, g, b])

    # Dead zone band
    new_pts.extend([neg_eps, cr, cg, cb])
    new_pts.extend([center, cr, cg, cb])
    new_pts.extend([pos_eps, cr, cg, cb])

    # Remap right: (center, vmax] → [pos_eps, vmax]
    if right_pts:
        old_range = vmax - center
        new_range = vmax - pos_eps
        for x, r, g, b in right_pts:
            if old_range != 0:
                t = (x - center) / old_range
                nx = pos_eps + t * new_range
            else:
                nx = vmax
            new_pts.extend([nx, r, g, b])

    return new_pts


def apply_symlog(ctf, linthresh, linear_rgb_points=None, n_samples=256, epsilon=0.0):
    """Build a symlog CTF with decade control points.

    Control points are placed at powers of 10 (and ±linthresh, 0 for
    mixed-sign data).  The RGB color for each control point is sampled
    from the linear colorbar at the position where that value falls in
    symlog space: t = (symlog(v) - symlog(min)) / (symlog(max) - symlog(min)).

    When *epsilon* > 0 (diverging mode), a dead zone is injected around
    zero.  Control points in (0, vmax] are compressed into [+eps, vmax]
    and points in [vmin, 0) into [vmin, -eps].  The band [-eps, +eps]
    is held at the center color.  All original colors are retained —
    they are squeezed outward from the dead zone rather than discarded.

    Args:
        ctf: vtkColorTransferFunction.
        linthresh: Linear threshold for symlog transformation.
        linear_rgb_points: RGB control points from the linear LUT.
        n_samples: Number of uniform samples in symlog space for building the CTF.
        epsilon: Half-width of the dead zone around zero (data-space units).

    Returns:
        Tuple of (lut_img_h, lut_img_v) base64 PNG strings, or None if
        the range is zero.
    """
    x_min, x_max = ctf.GetRange()
    data_range = x_max - x_min
    if data_range == 0:
        return None

    def symlog(v):
        """Symmetric log: sign(v) * log10(1 + |v|/linthresh)."""
        v = np.asarray(v, dtype=float)
        return np.sign(v) * np.log10(1.0 + np.abs(v) / linthresh)

    # Build control points: N uniform samples in symlog space, plus
    # mandatory breakpoints at ±linthresh and 0 for exact transitions.
    s_min_val = float(symlog(x_min))
    s_max_val = float(symlog(x_max))
    s_range_bp = s_max_val - s_min_val
    if s_range_bp == 0:
        return None

    # Uniform in symlog space → invert to data space
    s_vals = np.linspace(s_min_val, s_max_val, n_samples)
    breakpoints = []
    for s in s_vals:
        v = float(np.sign(s) * linthresh * (10.0 ** abs(s) - 1.0))
        v = max(x_min, min(x_max, v))
        breakpoints.append(v)

    # Symlog range for normalization
    s_min = float(symlog(x_min))
    s_max = float(symlog(x_max))
    s_range = s_max - s_min
    if s_range == 0:
        return None

    # Build a standalone linear CTF for safe color sampling
    linear_ctf = vtkColorTransferFunction()
    if linear_rgb_points:
        src = linear_rgb_points
    else:
        src = get_rgb_points(ctf)
    for i in range(0, len(src), 4):
        linear_ctf.AddRGBPoint(src[i], src[i + 1], src[i + 2], src[i + 3])

    # Sample RGB from the linear CTF at symlog-normalized positions
    rgb = [0.0, 0.0, 0.0]
    new_rgb_points = []
    display_rgb_points = []
    for v in breakpoints:
        t = (float(symlog(v)) - s_min) / s_range
        x_lookup = x_min + t * data_range
        linear_ctf.GetColor(x_lookup, rgb)
        r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])
        new_rgb_points.extend([float(v), r, g, b])
        # Display points: uniform linear positions with symlog colors
        display_rgb_points.extend([x_lookup, r, g, b])

    # --- Inject epsilon dead zone in symlog space ---
    eps = max(0.0, float(epsilon))
    if eps > 0 and x_min < 0 < x_max:
        # Sample center color from the unmodified points at x=0
        center_t = (float(symlog(0.0)) - s_min) / s_range
        center_lookup = x_min + center_t * data_range
        linear_ctf.GetColor(center_lookup, rgb)
        cr, cg, cb = float(rgb[0]), float(rgb[1]), float(rgb[2])

        # Display-space positions of center and ±epsilon
        s_eps_pos = float(symlog(eps))
        s_eps_neg = float(symlog(-eps))
        d_center = center_lookup
        d_eps_pos = x_min + (s_eps_pos - s_min) / s_range * data_range
        d_eps_neg = x_min + (s_eps_neg - s_min) / s_range * data_range

        # Remap rendering points (data space, center=0)
        new_rgb_points = _remap_with_dead_zone(
            new_rgb_points,
            x_min,
            x_max,
            0.0,
            -eps,
            eps,
            cr,
            cg,
            cb,
        )
        # Remap display points (display space, asymmetric boundaries)
        display_rgb_points = _remap_with_dead_zone(
            display_rgb_points,
            x_min,
            x_max,
            d_center,
            d_eps_neg,
            d_eps_pos,
            cr,
            cg,
            cb,
        )

    # Regenerate colorbar image from display points so it matches the 3D
    set_rgb_points(ctf, display_rgb_points)
    lut_img = lut_to_img_h(ctf)
    lut_img_v = lut_to_img_v(ctf)

    # Store rendering points on the CTF — the actual CTF used by the
    # mapper is a standalone vtkColorTransferFunction built in
    # update_color_preset.
    set_rgb_points(ctf, new_rgb_points)

    return lut_img, lut_img_v


def apply_discrete_symlog(
    ctf,
    linthresh,
    linear_rgb_points,
    n_sub=1,
    n_samples=256,
    epsilon=0.0,
):
    """Build a discrete (stepped) symlog CTF.

    Each decade interval is split into *n_sub* equal sub-bands in symlog
    space, each with a flat color sampled from the continuous LUT at the
    sub-band midpoint.  Twin control points with a tiny offset create hard
    steps at the sub-band boundaries.  The display image is also replaced
    with a banded colorbar.

    When *epsilon* > 0, the finished discrete bands are remapped to
    inject a dead zone around zero (same approach as ``apply_symlog``).

    Args:
        ctf: vtkColorTransferFunction.
        linthresh: Linear threshold for symlog transformation.
        linear_rgb_points: RGB control points from the linear LUT.
        n_sub: Number of sub-bands per decade interval.
        n_samples: Number of uniform samples in symlog space for building the CTF.
        epsilon: Half-width of the dead zone around zero (data-space units).

    Returns:
        Tuple of (display_rgb_points, discrete_tick_data, lut_img_h,
        lut_img_v) or (None, None, None, None) if the range is zero.
    """
    x_min, x_max = ctf.GetRange()
    data_range = x_max - x_min
    if data_range == 0:
        return None, None, None, None

    def symlog(v):
        """Symmetric log: sign(v) * log10(1 + |v|/linthresh)."""
        v = np.asarray(v, dtype=float)
        return np.sign(v) * np.log10(1.0 + np.abs(v) / linthresh)

    # Build decade boundaries (same logic as symlog ticks)
    boundaries = set()
    if x_min < 0:
        lo = max(linthresh, 1e-30)
        for e in range(
            int(np.floor(np.log10(lo))),
            int(np.floor(np.log10(abs(x_min)))) + 1,
        ):
            val = -(10.0**e)
            if x_min <= val < 0:
                boundaries.add(val)
    if x_max > 0:
        lo = max(linthresh, 1e-30)
        for e in range(
            int(np.floor(np.log10(lo))),
            int(np.floor(np.log10(x_max))) + 1,
        ):
            val = 10.0**e
            if 0 < val <= x_max:
                boundaries.add(val)
    if x_min < 0 and x_max > 0:
        boundaries.update((-linthresh, 0.0, linthresh))
    elif x_min < 0 and x_max <= 0:
        if -linthresh >= x_min:
            boundaries.add(-linthresh)
    elif x_min >= 0 and x_max > 0:
        if linthresh <= x_max:
            boundaries.add(linthresh)
    if x_min <= 0 <= x_max:
        boundaries.add(0.0)
    boundaries.add(x_min)
    boundaries.add(x_max)
    # Filter to only values within [x_min, x_max]
    boundaries = sorted(b for b in boundaries if x_min <= b <= x_max)

    if len(boundaries) < 2:
        return None, None, None, None

    # Symlog range for normalization
    s_min = float(symlog(x_min))
    s_max = float(symlog(x_max))
    s_range = s_max - s_min
    if s_range == 0:
        return None, None, None, None

    # Store boundary values and their display positions (%) for tick alignment.
    all_tick_data = []
    for bv in boundaries[1:-1]:
        s_val = float(symlog(bv))
        pct = (s_val - s_min) / s_range * 100
        all_tick_data.append({"val": bv, "pos": float(pct)})

    if x_min < 0:
        # Exclude linthresh / -linthresh from tick labels
        lt = float(linthresh)
        filtered = [t for t in all_tick_data if abs(abs(t["val"]) - lt) > 1e-12]
        # Separate into negative, zero, and positive
        neg = [t for t in filtered if t["val"] < 0]
        zero = [t for t in filtered if t["val"] == 0]
        pos = [t for t in filtered if t["val"] > 0]
        # Keep every other decade tick moving outward from 0
        neg_outward = list(reversed(neg))
        thinned_neg = [neg_outward[i] for i in range(0, len(neg_outward), 2)]
        thinned_pos = [pos[i] for i in range(0, len(pos), 2)]
        discrete_tick_data = sorted(thinned_neg + zero + thinned_pos, key=lambda t: t["val"])
    else:
        discrete_tick_data = all_tick_data

    # Build a continuous symlog CTF so discrete bands sample colours that
    # match the continuous rendering.
    linear_ctf = vtkColorTransferFunction()
    for i in range(0, len(linear_rgb_points), 4):
        linear_ctf.AddRGBPoint(
            linear_rgb_points[i],
            linear_rgb_points[i + 1],
            linear_rgb_points[i + 2],
            linear_rgb_points[i + 3],
        )

    s_vals = np.linspace(s_min, s_max, n_samples)
    symlog_ctf = vtkColorTransferFunction()
    rgb_tmp = [0.0, 0.0, 0.0]
    for s in s_vals:
        v = float(np.sign(s) * linthresh * (10.0 ** abs(s) - 1.0))
        v = max(x_min, min(x_max, v))
        t = (s - s_min) / s_range
        x_lookup = x_min + t * data_range
        linear_ctf.GetColor(x_lookup, rgb_tmp)
        symlog_ctf.AddRGBPoint(v, rgb_tmp[0], rgb_tmp[1], rgb_tmp[2])

    # For each decade interval, split into n_sub equal sub-bands in
    # symlog space.
    rgb = [0.0, 0.0, 0.0]
    eps_data = (x_max - x_min) * 1e-9
    eps_lin = data_range * 1e-9
    display_rgb_points = []
    render_rgb_points = []
    band_idx = 0
    total_bands = (len(boundaries) - 1) * n_sub
    for i in range(len(boundaries) - 1):
        s_lo_decade = float(symlog(boundaries[i]))
        s_hi_decade = float(symlog(boundaries[i + 1]))
        for j in range(n_sub):
            # Sub-band edges in symlog space
            s_lo = s_lo_decade + (s_hi_decade - s_lo_decade) * j / n_sub
            s_hi = s_lo_decade + (s_hi_decade - s_lo_decade) * (j + 1) / n_sub
            s_mid = (s_lo + s_hi) / 2.0

            # Invert symlog to get data-space values
            v_mid = float(np.sign(s_mid) * linthresh * (10.0 ** abs(s_mid) - 1.0))
            v_mid = max(x_min, min(x_max, v_mid))
            symlog_ctf.GetColor(v_mid, rgb)
            r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])

            # Invert symlog to get data-space boundaries for rendering
            v_lo = float(np.sign(s_lo) * linthresh * (10.0 ** abs(s_lo) - 1.0))
            v_hi = float(np.sign(s_hi) * linthresh * (10.0 ** abs(s_hi) - 1.0))
            v_lo = max(x_min, min(x_max, v_lo))
            v_hi = max(x_min, min(x_max, v_hi))

            # Linear positions for display image
            t_lo_pos = (s_lo - s_min) / s_range
            t_hi_pos = (s_hi - s_min) / s_range
            d_lo = x_min + t_lo_pos * data_range
            d_hi = x_min + t_hi_pos * data_range

            is_first = band_idx == 0
            is_last = band_idx == total_bands - 1

            if is_first:
                display_rgb_points.extend([d_lo, r, g, b])
                render_rgb_points.extend([float(v_lo), r, g, b])
            else:
                display_rgb_points.extend([d_lo + eps_lin, r, g, b])
                render_rgb_points.extend([float(v_lo) + eps_data, r, g, b])

            if is_last:
                display_rgb_points.extend([d_hi, r, g, b])
                render_rgb_points.extend([float(v_hi), r, g, b])
            else:
                display_rgb_points.extend([d_hi - eps_lin, r, g, b])
                render_rgb_points.extend([float(v_hi) - eps_data, r, g, b])

            band_idx += 1

    # --- Inject epsilon dead zone ---
    dead_eps = max(0.0, float(epsilon))
    if dead_eps > 0 and x_min < 0 < x_max:
        # Sample center color from the linear CTF at symlog(0)
        center_t = (float(symlog(0.0)) - s_min) / s_range
        center_lookup = x_min + center_t * data_range
        rgb_center = [0.0, 0.0, 0.0]
        linear_ctf.GetColor(center_lookup, rgb_center)
        cr = float(rgb_center[0])
        cg = float(rgb_center[1])
        cb = float(rgb_center[2])

        # Display-space positions of center and ±epsilon
        s_eps_pos = float(symlog(dead_eps))
        s_eps_neg = float(symlog(-dead_eps))
        d_center = center_lookup
        d_eps_pos = x_min + (s_eps_pos - s_min) / s_range * data_range
        d_eps_neg = x_min + (s_eps_neg - s_min) / s_range * data_range

        render_rgb_points = _remap_with_dead_zone(
            render_rgb_points,
            x_min,
            x_max,
            0.0,
            -dead_eps,
            dead_eps,
            cr,
            cg,
            cb,
        )
        display_rgb_points = _remap_with_dead_zone(
            display_rgb_points,
            x_min,
            x_max,
            d_center,
            d_eps_neg,
            d_eps_pos,
            cr,
            cg,
            cb,
        )

    # Generate the discrete banded colorbar image
    set_rgb_points(ctf, display_rgb_points)
    lut_img = lut_to_img_h(ctf)
    lut_img_v = lut_to_img_v(ctf)

    # Set rendering points on the CTF
    set_rgb_points(ctf, render_rgb_points)

    return display_rgb_points, discrete_tick_data, lut_img, lut_img_v
