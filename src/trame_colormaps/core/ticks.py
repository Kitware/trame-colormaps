"""Colorbar tick computation.

Pure numpy functions for computing nicely spaced tick marks on colorbars
with linear, log, and symlog scales.
"""

import numpy as np


def get_nice_ticks(vmin, vmax, n, scale="linear", linthresh=None, min_gap=None, desired_n=None):
    """Compute nicely spaced tick values for a given range and scale.

    Args:
        vmin: Minimum data value.
        vmax: Maximum data value.
        n: Desired number of ticks.
        scale: One of 'linear', 'log', or 'symlog'.
        linthresh: Linear threshold for log/symlog scales. Used as the
            floor for safe log computation. Defaults to 1e-15 for log,
            1.0 for symlog.

    Returns:
        Sorted array of unique, snapped tick values.
    """

    def snap(val):
        """Round val to the nearest 'nice' number (1, 2, 5, or 10 × 10^N)."""
        if np.isclose(val, 0, atol=1e-12):
            return 0.0
        sign = np.sign(val)
        val_abs = abs(val)
        mag = 10 ** np.floor(np.log10(val_abs))
        residual = val_abs / mag
        nice_steps = np.array([1.0, 2.0, 5.0, 10.0])
        best_step = nice_steps[np.abs(nice_steps - residual).argmin()]
        return sign * best_step * mag

    if scale == "linear":
        raw_ticks = np.linspace(vmin, vmax, n)
    elif scale == "log":
        # Use only integer powers of 10 that fall inside [vmin, vmax].
        # Never fall back to geomspace — log ticks should always be decades.
        log_floor = linthresh if linthresh is not None else 1e-15
        safe_vmin = max(vmin, log_floor)
        safe_vmax = max(vmax, log_floor)
        start_exp = int(np.floor(np.log10(safe_vmin)))
        stop_exp = int(np.ceil(np.log10(safe_vmax)))
        powers = [
            10.0**e
            for e in range(start_exp, stop_exp + 1)
            if safe_vmin <= 10.0**e <= safe_vmax
        ]
        raw_ticks = np.array(powers) if powers else np.array([])
    elif scale == "symlog":
        if linthresh is None:
            linthresh = 1.0
        # Use powers of 10 as tick values, matching the LUT breakpoints.
        # Collect negative and positive exponents separately so we can
        # stride each side independently when the decade span is large.
        lo = max(linthresh, 1e-30)
        neg_exps = []
        pos_exps = []
        if vmin < 0:
            e_lo = int(np.floor(np.log10(lo)))
            e_hi = int(np.floor(np.log10(abs(vmin))))
            neg_exps = list(range(e_lo, e_hi + 1))
        if vmax > 0:
            e_lo = int(np.floor(np.log10(lo)))
            e_hi = int(np.floor(np.log10(vmax)))
            pos_exps = list(range(e_lo, e_hi + 1))

        # Build a symlog mapping to filter ticks by visual spacing.
        # Powers near zero are compressed into a tiny region, so they
        # need a larger stride; powers far from zero get more space and
        # should keep a smaller stride.  We achieve this by computing
        # the symlog position of each candidate and only keeping those
        # that are separated by at least `min_pos_gap` in position space.
        def _symlog(v):
            return np.sign(v) * np.log10(1.0 + np.abs(v) / lo)

        s_min = _symlog(vmin)
        s_max = _symlog(vmax)
        s_range = s_max - s_min if s_max != s_min else 1.0

        # Target gap in 0-100 position space.  Use the original desired
        # tick count (not the inflated raw_n) and at least min_gap so
        # ticks don't cluster after the downstream filter.
        dn = desired_n if desired_n is not None else n
        min_pos_gap = max(100.0 / max(dn, 4), min_gap if min_gap is not None else 7)

        # Collect all candidate exponents as (value, position) sorted
        # from most negative to most positive.
        all_vals = []
        for e in neg_exps:
            val = -(10.0**e)
            if vmin <= val < 0:
                pos = (_symlog(val) - s_min) / s_range * 100
                all_vals.append((val, pos))
        if vmin <= 0 <= vmax:
            pos = (_symlog(0.0) - s_min) / s_range * 100
            all_vals.append((0.0, pos))
        for e in pos_exps:
            val = 10.0**e
            if 0 < val <= vmax:
                pos = (_symlog(val) - s_min) / s_range * 100
                all_vals.append((val, pos))
        all_vals.sort(key=lambda x: x[1])

        # Greedy filter: always keep zero, then keep ticks that are
        # far enough apart in position space from the last kept tick.
        # Work outward from zero so the most visually important ticks
        # (large magnitude) get priority.
        zero_idx = None
        for i, (val, _) in enumerate(all_vals):
            if val == 0.0:
                zero_idx = i
                break

        kept = set()
        if zero_idx is not None:
            kept.add(zero_idx)
            # Scan rightward (positive side, increasing magnitude)
            last_pos = all_vals[zero_idx][1]
            for i in range(zero_idx + 1, len(all_vals)):
                if all_vals[i][1] - last_pos >= min_pos_gap:
                    kept.add(i)
                    last_pos = all_vals[i][1]
            # Scan leftward (negative side, increasing magnitude)
            last_pos = all_vals[zero_idx][1]
            for i in range(zero_idx - 1, -1, -1):
                if last_pos - all_vals[i][1] >= min_pos_gap:
                    kept.add(i)
                    last_pos = all_vals[i][1]
        else:
            # No zero — simple left-to-right scan
            last_pos = -np.inf
            for i in range(len(all_vals)):
                if all_vals[i][1] - last_pos >= min_pos_gap:
                    kept.add(i)
                    last_pos = all_vals[i][1]

        raw_ticks = np.array(sorted(all_vals[i][0] for i in kept))
        # Skip snap — powers of 10 are already nice
        return raw_ticks
    else:
        raw_ticks = np.linspace(vmin, vmax, n)

    nice_ticks = np.array([snap(t) for t in raw_ticks])

    # Force 0 for non-log scales if it's within range
    if vmin <= 0 <= vmax and scale != "log":
        idx = np.abs(nice_ticks).argmin()
        nice_ticks[idx] = 0.0

    return np.unique(np.sort(nice_ticks))


def format_tick(val):
    """Format a tick value as a concise human-readable string.

    Returns a string suitable for display on a colorbar. Powers of 10 are
    shown as '10^N', very large/small values use scientific notation, and
    intermediate values use fixed-point.
    """
    if val == 0:
        return "0"

    val_abs = abs(val)
    log10 = np.log10(val_abs)

    if np.isclose(log10, np.round(log10), atol=1e-12):
        exponent = int(np.round(log10))
        sign = "-" if val < 0 else ""
        if exponent == 0:
            return f"{sign}1"
        if exponent == 1:
            return f"{sign}10"
        return f"{sign}10^{exponent}"

    if val_abs >= 1000 or val_abs <= 0.01:
        return f"{val:.1e}"
    return f"{int(val) if val == int(val) else val:.1f}"


def tick_contrast_color(r, g, b):
    """Return '#fff' or '#000' for best contrast against the given RGB color.

    Uses the W3C relative luminance formula to decide. RGB values are
    expected in [0, 1] range.
    """
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#000" if luminance > 0.45 else "#fff"


def compute_color_ticks(
    vmin, vmax, scale="linear", n=5, min_gap=7, edge_margin=3, linthresh=None
):
    """Compute tick marks for a colorbar.

    Tick positions are computed in the space matching the scale:
    - linear: position = (val - vmin) / (vmax - vmin) * 100
    - symlog: position = (symlog(val) - symlog(vmin)) / (symlog(vmax) - symlog(vmin)) * 100

    The colorbar image is always the linear preset, so symlog ticks
    appear at different positions than linear ticks for the same values.

    Args:
        vmin: Minimum color range value
        vmax: Maximum color range value
        scale: One of 'linear', 'log', or 'symlog'
        n: Desired number of ticks
        min_gap: Minimum gap between ticks in percentage points
        edge_margin: Minimum distance from edges (0% and 100%) in percentage points.
        linthresh: Linear threshold for log/symlog scales.

    Returns:
        List of dicts with 'position' (0-100 percentage) and 'label' keys.
    """
    if vmin >= vmax:
        return []

    raw_n = n if scale == "linear" else n * 2
    ticks = get_nice_ticks(vmin, vmax, raw_n, scale, linthresh=linthresh,
                           min_gap=min_gap, desired_n=n)
    data_range = vmax - vmin

    if scale == "symlog":
        if linthresh is None:
            linthresh = 1.0

        def _symlog_fn(v):
            v = np.asarray(v, dtype=float)
            return np.sign(v) * np.log10(1.0 + np.abs(v) / linthresh)

        s_min = float(_symlog_fn(vmin))
        s_max = float(_symlog_fn(vmax))
        s_range = s_max - s_min

    elif scale == "log":
        log_floor = linthresh if linthresh is not None else 1e-30
        safe_vmin = max(vmin, log_floor)
        safe_vmax = max(vmax, log_floor)
        _log_min = np.log10(safe_vmin)
        _log_max = np.log10(safe_vmax)
        _log_range = _log_max - _log_min

    # Build candidate list with position in the appropriate space
    candidates = []
    has_zero = False
    for t in ticks:
        val = float(t)
        if scale == "symlog" and s_range != 0:
            pos = (float(_symlog_fn(val)) - s_min) / s_range * 100
        elif scale == "log" and _log_range and _log_range != 0 and val > 0:
            pos = (np.log10(val) - _log_min) / _log_range * 100
        else:
            pos = (val - vmin) / data_range * 100
        if edge_margin <= pos <= (100 - edge_margin):
            is_zero = val == 0
            if is_zero:
                has_zero = True
            candidates.append(
                {
                    "position": round(pos, 2),
                    "label": format_tick(val),
                    "priority": is_zero,
                }
            )

    # Always include 0 when it falls within the range (for any scale),
    # but respect edge_margin so it doesn't overlap the min/max labels.
    if not has_zero and scale != "log":
        if scale == "symlog" and s_range != 0:
            zero_pos = (float(_symlog_fn(0.0)) - s_min) / s_range * 100
        else:
            zero_pos = (0.0 - vmin) / data_range * 100
        if edge_margin <= zero_pos <= (100 - edge_margin):
            tick = {"position": round(zero_pos, 2), "label": "0", "priority": True}
            # Insert in sorted order
            inserted = False
            for i, c in enumerate(candidates):
                if tick["position"] <= c["position"]:
                    candidates.insert(i, tick)
                    inserted = True
                    break
            if not inserted:
                candidates.append(tick)

    # Filter out ticks that are too close together, but never remove priority ticks
    result = []
    for tick in candidates:
        is_priority = tick.get("priority", False)
        if is_priority:
            if result and (tick["position"] - result[-1]["position"]) < min_gap:
                if not result[-1].get("priority", False):
                    result.pop()
            result.append(tick)
        elif not result or (tick["position"] - result[-1]["position"]) >= min_gap:
            # Also check distance to next priority tick (look-ahead)
            result.append(tick)

    # Clean up internal flags before returning
    for tick in result:
        tick.pop("priority", None)
    return result
