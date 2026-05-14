"""LUT transform operations for color transfer functions.

Provides functions that operate on vtkColorTransferFunction objects to apply:
- Linear presets (with optional inversion)
- Discrete linear banding
- Log scale mapping
- Discrete log banding
- Symlog (symmetric log) mapping
- Discrete symlog banding

These functions are designed to be called by the ColormapController but
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
    map_to_log_space,
    rescale_ctf,
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


def apply_discrete_linear(ctf, linear_rgb_points, n_sub=1, n_intervals=4):
    """Build a discrete (stepped) linear LUT.

    The data range is divided into *n_intervals* equal-percentage intervals.
    Each interval is then split into *n_sub* equal sub-bands, each with a
    flat color sampled from the continuous linear LUT at the sub-band
    midpoint.  The boundary values are stored so tick computation can
    place tick marks at the exact same positions.

    Args:
        ctf: vtkColorTransferFunction.
        linear_rgb_points: RGB control points from the linear LUT.
        n_sub: Number of sub-bands per interval.
        n_intervals: Number of equal-percentage intervals to divide the range into.

    Returns:
        Tuple of (display_rgb_points, discrete_tick_data, lut_img) or
        (None, None) if the data range is zero.
    """

    N_INTERVALS = n_intervals
    x_min, x_max = ctf.GetRange()
    data_range = x_max - x_min
    if data_range == 0:
        return None, None

    # Evenly spaced boundaries (percentages of data range)
    boundaries = [x_min + data_range * i / N_INTERVALS for i in range(N_INTERVALS + 1)]
    # Store boundary values and their display positions (%) for tick alignment
    discrete_tick_data = [
        {"val": boundaries[i], "pos": i / N_INTERVALS * 100}
        for i in range(1, N_INTERVALS)
    ]

    if len(boundaries) < 2:
        return None, None

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

    return display_rgb_points, discrete_tick_data, lut_img, lut_img_v


def apply_log(ctf, linthresh):
    """Transform the already-prepared CTF to log scale.

    Uses linthresh (smallest positive non-zero data value) as the floor
    when the range includes zero or negative values.
    The colorbar image is captured before this call, so it stays linear.

    Args:
        ctf: vtkColorTransferFunction.
        linthresh: Linear threshold (smallest positive non-zero data value).
    """
    x_min, x_max = ctf.GetRange()
    if x_max <= 0:
        return
    if x_min <= 0:
        x_min = linthresh
        rescale_ctf(ctf, x_min, x_max)
    map_to_log_space(ctf)


def apply_discrete_log(ctf, linthresh, linear_rgb_points, n_sub=1, n_samples=256):
    """Build a discrete (stepped) log-scale LUT.

    Decade boundaries are powers of 10 from linthresh to x_max.
    Each decade is split into *n_sub* equal sub-bands in log space,
    each with a flat color sampled from the continuous linear LUT.

    Args:
        ctf: vtkColorTransferFunction.
        linthresh: Linear threshold for the log floor.
        linear_rgb_points: RGB control points from the linear LUT.
        n_sub: Number of sub-bands per decade.
        n_samples: Number of uniform samples for building the continuous log CTF.

    Returns:
        Tuple of (display_rgb_points, discrete_tick_data, lut_img) or
        (None, None, None) if the range is invalid.
    """
    x_min, x_max = ctf.GetRange()
    if x_max <= 0:
        return None, None, None
    # Clamp floor
    x_min = max(x_min, linthresh)
    data_range = x_max - x_min
    if data_range == 0:
        return None, None, None

    log_min = np.log10(x_min)
    log_max = np.log10(x_max)
    log_range = log_max - log_min
    if log_range == 0:
        return None, None, None

    # Build decade boundaries
    boundaries = [x_min]
    e_lo = int(np.ceil(np.log10(x_min)))
    e_hi = int(np.floor(np.log10(x_max)))
    for e in range(e_lo, e_hi + 1):
        val = 10.0**e
        if x_min < val < x_max:
            boundaries.append(val)
    boundaries.append(x_max)

    if len(boundaries) < 2:
        return None, None, None

    # Store boundary values and their display positions (%) for tick alignment
    log_range_val = log_max - log_min
    discrete_tick_data = []
    for bv in boundaries[1:-1]:
        pct = (np.log10(bv) - log_min) / log_range_val * 100 if log_range_val else 0
        discrete_tick_data.append({"val": bv, "pos": float(pct)})

    # Build a continuous log CTF so discrete bands sample colours that
    # match the continuous log rendering.
    linear_ctf = vtkColorTransferFunction()
    for i in range(0, len(linear_rgb_points), 4):
        linear_ctf.AddRGBPoint(
            linear_rgb_points[i],
            linear_rgb_points[i + 1],
            linear_rgb_points[i + 2],
            linear_rgb_points[i + 3],
        )
    log_vals = np.linspace(log_min, log_max, n_samples)
    log_ctf = vtkColorTransferFunction()
    rgb_tmp = [0.0, 0.0, 0.0]
    for lg in log_vals:
        v = 10.0**lg
        v = max(x_min, min(x_max, v))
        t = (lg - log_min) / log_range
        x_lookup = x_min + t * data_range
        linear_ctf.GetColor(x_lookup, rgb_tmp)
        log_ctf.AddRGBPoint(v, rgb_tmp[0], rgb_tmp[1], rgb_tmp[2])

    rgb = [0.0, 0.0, 0.0]
    eps_data = data_range * 1e-9
    eps_lin = data_range * 1e-9
    display_rgb_points = []
    render_rgb_points = []
    band_idx = 0
    total_bands = (len(boundaries) - 1) * n_sub
    for i in range(len(boundaries) - 1):
        log_lo_decade = np.log10(boundaries[i])
        log_hi_decade = np.log10(boundaries[i + 1])
        for j in range(n_sub):
            # Sub-band edges in log space
            log_lo = log_lo_decade + (log_hi_decade - log_lo_decade) * j / n_sub
            log_hi = log_lo_decade + (log_hi_decade - log_lo_decade) * (j + 1) / n_sub
            log_mid = (log_lo + log_hi) / 2.0
            # Sample color from continuous log CTF at sub-band midpoint
            v_mid = 10.0**log_mid
            v_mid = max(x_min, min(x_max, v_mid))
            log_ctf.GetColor(v_mid, rgb)
            r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])

            # Data-space boundaries for rendering
            v_lo = 10.0**log_lo
            v_hi = 10.0**log_hi
            v_lo = max(x_min, min(x_max, v_lo))
            v_hi = max(x_min, min(x_max, v_hi))

            # Linear positions for display image
            t_lo_pos = (log_lo - log_min) / log_range
            t_hi_pos = (log_hi - log_min) / log_range
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

    # Generate the discrete banded colorbar image
    set_rgb_points(ctf, display_rgb_points)
    lut_img = lut_to_img_h(ctf)
    lut_img_v = lut_to_img_v(ctf)

    # Set rendering points on the CTF
    set_rgb_points(ctf, render_rgb_points)

    return display_rgb_points, discrete_tick_data, lut_img, lut_img_v


def apply_symlog(ctf, linthresh, linear_rgb_points=None, n_samples=256):
    """Build a symlog CTF with decade control points.

    Control points are placed at powers of 10 (and ±linthresh, 0 for
    mixed-sign data).  The RGB color for each control point is sampled
    from the linear colorbar at the position where that value falls in
    symlog space: t = (symlog(v) - symlog(min)) / (symlog(max) - symlog(min)).

    Args:
        ctf: vtkColorTransferFunction.
        linthresh: Linear threshold for symlog transformation.
        linear_rgb_points: RGB control points from the linear LUT.
        n_samples: Number of uniform samples in symlog space for building the CTF.

    Returns:
        Base64 PNG colorbar image string, or None if the range is zero.
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

    # Regenerate colorbar image from display points so it matches the 3D
    set_rgb_points(ctf, display_rgb_points)
    lut_img = lut_to_img_h(ctf)
    lut_img_v = lut_to_img_v(ctf)

    # Store rendering points on the CTF — the actual CTF used by the
    # mapper is a standalone vtkColorTransferFunction built in
    # update_color_preset.
    set_rgb_points(ctf, new_rgb_points)

    return lut_img, lut_img_v


def apply_discrete_symlog(ctf, linthresh, linear_rgb_points, n_sub=1, n_samples=256):
    """Build a discrete (stepped) symlog CTF.

    Each decade interval is split into *n_sub* equal sub-bands in symlog
    space, each with a flat color sampled from the continuous LUT at the
    sub-band midpoint.  Twin control points with a tiny offset create hard
    steps at the sub-band boundaries.  The display image is also replaced
    with a banded colorbar.

    Args:
        ctf: vtkColorTransferFunction.
        linthresh: Linear threshold for symlog transformation.
        linear_rgb_points: RGB control points from the linear LUT.
        n_sub: Number of sub-bands per decade interval.
        n_samples: Number of uniform samples in symlog space for building the CTF.

    Returns:
        Tuple of (display_rgb_points, discrete_tick_data, lut_img) or
        (None, None, None) if the range is zero.
    """
    x_min, x_max = ctf.GetRange()
    data_range = x_max - x_min
    if data_range == 0:
        return None, None, None

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
        return None, None, None

    # Symlog range for normalization
    s_min = float(symlog(x_min))
    s_max = float(symlog(x_max))
    s_range = s_max - s_min
    if s_range == 0:
        return None, None, None

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
        discrete_tick_data = sorted(
            thinned_neg + zero + thinned_pos, key=lambda t: t["val"]
        )
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

    # Generate the discrete banded colorbar image
    set_rgb_points(ctf, display_rgb_points)
    lut_img = lut_to_img_h(ctf)
    lut_img_v = lut_to_img_v(ctf)

    # Set rendering points on the CTF
    set_rgb_points(ctf, render_rgb_points)

    return display_rgb_points, discrete_tick_data, lut_img, lut_img_v
