"""Tests for trame_colormaps.core.ticks."""

import numpy as np

from trame_colormaps.core.ticks import (
    compute_color_ticks,
    format_tick,
    get_nice_ticks,
    tick_contrast_color,
)

# --- format_tick ---


class TestFormatTick:
    def test_zero(self):
        assert format_tick(0) == "0"

    def test_one(self):
        assert format_tick(1) == "1"

    def test_negative_one(self):
        assert format_tick(-1) == "-1"

    def test_ten(self):
        assert format_tick(10) == "10"

    def test_negative_ten(self):
        assert format_tick(-10) == "-10"

    def test_power_of_ten_positive(self):
        assert format_tick(1000) == "10^3"

    def test_power_of_ten_negative(self):
        assert format_tick(-1000) == "-10^3"

    def test_small_power_of_ten(self):
        assert format_tick(0.001) == "10^-3"

    def test_large_value_scientific(self):
        result = format_tick(12345)
        assert "e" in result.lower()

    def test_small_value_scientific(self):
        result = format_tick(0.005)
        assert "e" in result.lower()

    def test_intermediate_value(self):
        result = format_tick(42.3)
        assert result == "42.3"

    def test_integer_value(self):
        result = format_tick(5.0)
        assert result in ("5", "5.0")


# --- tick_contrast_color ---


class TestTickContrastColor:
    def test_white_background(self):
        assert tick_contrast_color(1.0, 1.0, 1.0) == "#000"

    def test_black_background(self):
        assert tick_contrast_color(0.0, 0.0, 0.0) == "#fff"

    def test_mid_gray(self):
        result = tick_contrast_color(0.5, 0.5, 0.5)
        assert result in ("#000", "#fff")

    def test_bright_yellow(self):
        # High luminance → black text
        assert tick_contrast_color(1.0, 1.0, 0.0) == "#000"

    def test_dark_blue(self):
        # Low luminance → white text
        assert tick_contrast_color(0.0, 0.0, 0.5) == "#fff"


# --- get_nice_ticks ---


class TestGetNiceTicks:
    def test_linear_returns_sorted_unique(self):
        ticks = get_nice_ticks(0, 100, 5, scale="linear")
        assert len(ticks) > 0
        assert all(ticks[i] <= ticks[i + 1] for i in range(len(ticks) - 1))

    def test_linear_contains_endpoints_approx(self):
        ticks = get_nice_ticks(0, 100, 5, scale="linear")
        # Should snap near 0 and 100
        assert min(ticks) <= 5
        assert max(ticks) >= 95

    def test_linear_includes_zero_when_in_range(self):
        ticks = get_nice_ticks(-50, 50, 5, scale="linear")
        assert 0.0 in ticks

    def test_log_returns_powers_of_ten(self):
        ticks = get_nice_ticks(1, 10000, 5, scale="log")
        for t in ticks:
            log_val = np.log10(t)
            assert np.isclose(log_val, round(log_val)), f"{t} is not a power of 10"

    def test_log_within_range(self):
        ticks = get_nice_ticks(1, 10000, 5, scale="log")
        assert all(1 <= t <= 10000 for t in ticks)

    def test_symlog_includes_zero(self):
        ticks = get_nice_ticks(-1000, 1000, 10, scale="symlog", linthresh=1.0)
        assert 0.0 in ticks

    def test_symlog_has_negative_and_positive(self):
        ticks = get_nice_ticks(-1000, 1000, 10, scale="symlog", linthresh=1.0)
        assert any(t < 0 for t in ticks)
        assert any(t > 0 for t in ticks)

    def test_empty_for_equal_range(self):
        ticks = get_nice_ticks(5, 5, 5, scale="linear")
        # With equal vmin/vmax, all ticks snap to same value
        assert len(np.unique(ticks)) <= 1


# --- compute_color_ticks ---


class TestComputeColorTicks:
    def test_returns_list_of_dicts(self):
        result = compute_color_ticks(0, 100)
        assert isinstance(result, list)
        assert all(isinstance(t, dict) for t in result)

    def test_dict_has_position_and_label(self):
        result = compute_color_ticks(0, 100)
        for t in result:
            assert "position" in t
            assert "label" in t

    def test_positions_within_bounds(self):
        result = compute_color_ticks(0, 100, edge_margin=3)
        for t in result:
            assert 3 <= t["position"] <= 97

    def test_empty_for_invalid_range(self):
        assert compute_color_ticks(100, 0) == []
        assert compute_color_ticks(50, 50) == []

    def test_min_gap_respected(self):
        result = compute_color_ticks(0, 100, min_gap=10)
        for i in range(1, len(result)):
            gap = result[i]["position"] - result[i - 1]["position"]
            # Allow small tolerance for priority ticks (zero)
            assert gap >= 9.0, f"Gap {gap} between ticks {i - 1} and {i}"

    def test_log_scale(self):
        result = compute_color_ticks(1, 10000, scale="log")
        assert len(result) > 0
        for t in result:
            assert 0 <= t["position"] <= 100

    def test_symlog_scale(self):
        result = compute_color_ticks(-1000, 1000, scale="symlog", linthresh=1.0)
        assert len(result) > 0
        labels = [t["label"] for t in result]
        assert "0" in labels

    def test_no_priority_key_in_output(self):
        result = compute_color_ticks(-100, 100)
        for t in result:
            assert "priority" not in t
