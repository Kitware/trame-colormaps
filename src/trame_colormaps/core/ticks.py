"""Colorbar tick computation.

Pure numpy functions for computing nicely spaced tick marks on colorbars
with linear, log, and symlog scales.
"""

import numpy as np


def get_nice_ticks(vmin, vmax, n, scale="linear", linthresh=None):
    """Compute nicely spaced tick values for a given range and scale.

    For all scales the algorithm is:
      1. Place *major* ticks (powers of 10 for log/symlog, nice-step
         multiples for linear) using a greedy spacing rule.
      2. Optionally place 0 if the range spans negative to positive.
      3. Fill remaining gaps with *minor* ticks chosen from a niceness
         hierarchy (5 > 2.5/7.5 > 2–9).

    Args:
        vmin: Minimum data value.
        vmax: Maximum data value.
        n: Desired number of ticks.
        scale: One of ``'linear'``, ``'log'``, or ``'symlog'``.
        linthresh: Linear threshold for log/symlog scales.

    Returns:
        Sorted numpy array of tick values.
    """
    if scale == "linear":
        # Pick a "nice" step size: smallest value from {1, 2, 2.5, 5, 10}×10^k
        # that is ≥ the evenly-spaced step.
        data_range = vmax - vmin
        if data_range <= 0 or n < 2:
            return np.array([])
        raw_step = data_range / n
        # Find the smallest nice step ≥ raw_step
        exponent = np.floor(np.log10(raw_step))
        base = 10.0**exponent
        nice_candidates = np.array([1.0, 2.0, 2.5, 5.0, 7.5, 10.0]) * base
        valid = nice_candidates[nice_candidates >= raw_step * (1 - 1e-9)]
        if len(valid) > 0:
            nice_step = valid[0]
        else:
            nice_step = nice_candidates[-1]
        # First tick: smallest multiple of nice_step > vmin
        first = np.ceil(vmin / nice_step) * nice_step
        if np.isclose(first, vmin, atol=nice_step * 1e-9):
            first += nice_step
        raw_ticks = np.arange(first, vmax, nice_step)
        # Filter out ticks too close to edges
        if len(raw_ticks) > 0:
            raw_ticks = raw_ticks[
                (raw_ticks > vmin + data_range * 0.01)
                & (raw_ticks < vmax - data_range * 0.01)
            ]
        # Priority: always include 0 if range spans negative to positive
        if vmin < 0 < vmax and not np.any(
            np.isclose(raw_ticks, 0.0, atol=nice_step * 1e-9)
        ):
            raw_ticks = np.sort(np.append(raw_ticks, 0.0))
        return raw_ticks
    elif scale == "log":
        # Positions use symlog-style transform: sign(v)*log10(1+|v|/linthresh).
        # Majors: powers of 10. Minors fill gaps ranked by niceness tier.
        lo = linthresh if linthresh is not None else 1.0
        safe_vmax = max(vmax, lo)

        def _log_pos(v):
            return np.sign(v) * np.log10(1.0 + np.abs(v) / lo)

        p_min = _log_pos(vmin)
        p_max = _log_pos(safe_vmax)
        p_range = p_max - p_min
        if p_range <= 0:
            return np.array([])

        min_pos_gap = 100.0 / max(n, 2)

        # Collect major ticks (powers of 10) across the full visible range
        # Use vmin/vmax (not linthresh) to determine decade range so we
        # don't miss powers of 10 between linthresh and vmax.
        abs_lo = max(lo, 1e-30)
        abs_hi = max(abs(vmin), abs(vmax), abs_lo)
        e_lo = int(np.floor(np.log10(abs_lo)))
        e_hi = int(np.floor(np.log10(abs_hi)))
        majors = []
        for e in range(e_lo, e_hi + 1):
            val = 10.0**e
            if val >= lo:
                pos = (_log_pos(val) - p_min) / p_range * 100
                if 0 <= pos <= 100:
                    majors.append((val, pos))

        # Step 1: greedy-select majors by 100/n spacing rule
        kept = []
        last_pos = -np.inf
        for val, pos in majors:
            if pos - last_pos >= min_pos_gap:
                kept.append((val, pos))
                last_pos = pos

        # After majors: include 0 if range spans negative and it fits
        if vmin < 0 < vmax:
            zero_pos = (_log_pos(0) - p_min) / p_range * 100
            if 0 <= zero_pos <= 100:
                fits = all(abs(zero_pos - kp) >= min_pos_gap * 0.5 for _, kp in kept)
                if fits:
                    kept.append((0, zero_pos))
        kept.sort(key=lambda x: x[1])

        # Step 2: collect minor ticks in visible range, ranked by niceness
        # Tier 0 (nicest): 5 × 10^k
        # Tier 1: 2.5, 7.5 × 10^k
        # Tier 2: 2, 3, 4, 6, 7, 8, 9 × 10^k
        minor_tiers = [
            [5],
            [2.5, 7.5],
            [2, 3, 4, 6, 7, 8, 9],
        ]
        major_vals = set(v for v, _ in majors)
        minors_by_tier = []  # list of (tier, val, pos)
        for tier_idx, mults in enumerate(minor_tiers):
            for e in range(e_lo, e_hi + 1):
                for m in mults:
                    val = m * 10.0**e
                    if val in major_vals:
                        continue
                    if val >= lo and val <= safe_vmax:
                        pos = (_log_pos(val) - p_min) / p_range * 100
                        if 0 <= pos <= 100:
                            minors_by_tier.append((tier_idx, val, pos))
        # Sort by tier first (nicest first), then by position
        minors_by_tier.sort(key=lambda x: (x[0], x[2]))

        # Step 3: fill gaps with minors, trying nicest first
        # Between two majors: need 2*step gap, 0.5*step margin each side
        # Edge to major or major to edge: need 1.5*step gap, 0.5*step margin
        half_gap = min_pos_gap * 0.5
        changed = True
        while changed:
            changed = False
            kept.sort(key=lambda x: x[1])
            anchors = [(None, 0.0)] + kept + [(None, 100.0)]
            for i in range(len(anchors) - 1):
                is_left_edge = anchors[i][0] is None
                is_right_edge = anchors[i + 1][0] is None
                gap_lo = anchors[i][1]
                gap_hi = anchors[i + 1][1]
                gap_size = gap_hi - gap_lo
                if is_left_edge or is_right_edge:
                    min_gap_needed = 1.5 * min_pos_gap
                else:
                    min_gap_needed = 2.0 * min_pos_gap
                if gap_size >= min_gap_needed:
                    for _tier, val, pos in minors_by_tier:
                        if pos > gap_lo and pos < gap_hi:
                            if pos - gap_lo >= half_gap and gap_hi - pos >= half_gap:
                                kept.append((val, pos))
                                changed = True
                                break  # one minor per gap, nicest wins
                if changed:
                    break  # restart with updated anchors

        kept.sort(key=lambda x: x[1])
        if len(kept) == 0:
            return np.array([])
        return np.array([v for v, _ in kept])
    elif scale == "symlog":
        if linthresh is None:
            linthresh = 1.0
        lo = max(linthresh, 1e-30)

        def _symlog(v):
            return np.sign(v) * np.log10(1.0 + np.abs(v) / lo)

        s_min = _symlog(vmin)
        s_max = _symlog(vmax)
        s_range = s_max - s_min if s_max != s_min else 1.0

        min_pos_gap = max(100.0 / max(n, 4), 7)
        half_gap = min_pos_gap * 0.5

        # --- Step 1: collect positive and negative majors (powers of 10) ---
        majors = []
        if vmin < 0:
            e_lo = int(np.floor(np.log10(lo)))
            e_hi = int(np.floor(np.log10(abs(vmin))))
            for e in range(e_lo, e_hi + 1):
                val = -(10.0**e)
                if vmin <= val < 0:
                    pos = (_symlog(val) - s_min) / s_range * 100
                    if 0 <= pos <= 100:
                        majors.append((val, pos))
        if vmax > 0:
            e_lo = int(np.floor(np.log10(lo)))
            e_hi = int(np.floor(np.log10(vmax)))
            for e in range(e_lo, e_hi + 1):
                val = 10.0**e
                if 0 < val <= vmax:
                    pos = (_symlog(val) - s_min) / s_range * 100
                    if 0 <= pos <= 100:
                        majors.append((val, pos))
        majors.sort(key=lambda x: x[1])

        # Greedy-select majors by spacing rule
        kept = []
        last_pos = -np.inf
        for val, pos in majors:
            if pos - last_pos >= min_pos_gap:
                kept.append((val, pos))
                last_pos = pos

        # --- Step 2: add 0 if it fits among majors ---
        if vmin <= 0 <= vmax:
            zero_pos = (_symlog(0.0) - s_min) / s_range * 100
            if 0 <= zero_pos <= 100:
                fits = all(abs(zero_pos - kp) >= half_gap for _, kp in kept)
                if fits:
                    kept.append((0.0, zero_pos))
        kept.sort(key=lambda x: x[1])

        # --- Step 3: fill gaps with minors (niceness-ranked) ---
        minor_tiers = [
            [5],
            [2.5, 7.5],
            [2, 3, 4, 6, 7, 8, 9],
        ]
        major_abs_vals = set(abs(v) for v, _ in majors)
        minors_by_tier = []
        abs_lo = lo
        abs_hi = max(abs(vmin), abs(vmax), lo)
        e_lo_m = int(np.floor(np.log10(abs_lo)))
        e_hi_m = int(np.floor(np.log10(abs_hi)))
        for tier_idx, mults in enumerate(minor_tiers):
            for e in range(e_lo_m, e_hi_m + 1):
                for m in mults:
                    base = m * 10.0**e
                    if base in major_abs_vals:
                        continue
                    # Try positive
                    if base >= lo and base <= vmax:
                        pos = (_symlog(base) - s_min) / s_range * 100
                        if 0 <= pos <= 100:
                            minors_by_tier.append((tier_idx, base, pos))
                    # Try negative
                    if -base >= vmin and -base <= 0:
                        neg_val = -base
                        pos = (_symlog(neg_val) - s_min) / s_range * 100
                        if 0 <= pos <= 100:
                            minors_by_tier.append((tier_idx, neg_val, pos))
        minors_by_tier.sort(key=lambda x: (x[0], x[2]))

        # Insert minors into gaps
        changed = True
        while changed:
            changed = False
            kept.sort(key=lambda x: x[1])
            anchors = [(None, 0.0)] + kept + [(None, 100.0)]
            for i in range(len(anchors) - 1):
                is_left_edge = anchors[i][0] is None
                is_right_edge = anchors[i + 1][0] is None
                gap_lo = anchors[i][1]
                gap_hi = anchors[i + 1][1]
                gap_size = gap_hi - gap_lo
                if is_left_edge or is_right_edge:
                    min_gap_needed = 1.5 * min_pos_gap
                else:
                    min_gap_needed = 2.0 * min_pos_gap
                if gap_size >= min_gap_needed:
                    for _tier, val, pos in minors_by_tier:
                        if pos > gap_lo and pos < gap_hi:
                            if pos - gap_lo >= half_gap and gap_hi - pos >= half_gap:
                                kept.append((val, pos))
                                changed = True
                                break  # one minor per gap, nicest wins
                if changed:
                    break  # restart with updated anchors

        kept.sort(key=lambda x: x[1])
        if len(kept) == 0:
            return np.array([])
        return np.array([v for v, _ in kept])
    else:
        return np.array([])


def format_tick(val):
    """Format a tick value as a concise human-readable string.

    Uses MeN notation (e.g. 5e2 for 500, 2.5e1 for 25) for large/small
    values.  Small integers and simple decimals are kept plain.
    """
    if val == 0:
        return "0"

    val_abs = abs(val)
    sign = "-" if val < 0 else ""

    # Plain integers
    if 1 <= val_abs < 10000 and np.isclose(val, round(val), atol=0):
        return str(int(round(val)))

    # Plain simple decimals
    if 0.01 <= val_abs < 1:
        return f"{val:g}"

    # MeN notation for large/small values
    exponent = int(np.floor(np.log10(val_abs)))
    mantissa = val_abs / 10.0**exponent
    # Format mantissa without trailing zeros
    m_str = f"{mantissa:g}"
    return f"{sign}{m_str}e{exponent}"


def format_log_tick(val):
    """Format a log tick value for display.  Always uses MeN notation."""
    if val == 0:
        return "0"
    val_abs = abs(val)
    sign = "-" if val < 0 else ""
    exponent = int(np.floor(np.log10(val_abs)))
    mantissa = val_abs / 10.0**exponent
    m_str = f"{mantissa:g}"
    return f"{sign}{m_str}e{exponent}"


def tick_contrast_color(r, g, b):
    """Return '#fff' or '#000' for best contrast against the given RGB color.

    Uses the W3C relative luminance formula to decide. RGB values are
    expected in [0, 1] range.
    """
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#000" if luminance > 0.45 else "#fff"
