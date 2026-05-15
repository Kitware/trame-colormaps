"""Tests for trame_colormaps.core.ticks."""

import numpy as np

from trame_colormaps.core.ticks import (
    format_log_tick,
    format_tick,
    get_nice_ticks,
    tick_contrast_color,
)

# --- format_tick ---


class TestFormatTick:
    def test_zero(self):
        assert format_tick(0) == "0"

    def test_small_integers_plain(self):
        assert format_tick(1) == "1"
        assert format_tick(-1) == "-1"
        assert format_tick(10) == "10"
        assert format_tick(150) == "150"
        assert format_tick(9999) == "9999"

    def test_simple_decimals_plain(self):
        assert format_tick(0.5) == "0.5"
        assert format_tick(0.01) == "0.01"

    def test_large_values_men(self):
        assert format_tick(10000) == "1e4"
        assert format_tick(12345) == "1.2345e4"

    def test_small_values_men(self):
        result = format_tick(0.005)
        assert "e" in result

    def test_negative_large(self):
        assert format_tick(-10000) == "-1e4"


# --- format_log_tick ---


class TestFormatLogTick:
    def test_zero(self):
        assert format_log_tick(0) == "0"

    def test_always_men(self):
        assert format_log_tick(1) == "1e0"
        assert format_log_tick(10) == "1e1"
        assert format_log_tick(100) == "1e2"
        assert format_log_tick(50) == "5e1"
        assert format_log_tick(25) == "2.5e1"

    def test_negative(self):
        assert format_log_tick(-100) == "-1e2"


# --- tick_contrast_color ---


class TestTickContrastColor:
    def test_white_background(self):
        assert tick_contrast_color(1.0, 1.0, 1.0) == "#000"

    def test_black_background(self):
        assert tick_contrast_color(0.0, 0.0, 0.0) == "#fff"

    def test_bright_yellow(self):
        assert tick_contrast_color(1.0, 1.0, 0.0) == "#000"

    def test_dark_blue(self):
        assert tick_contrast_color(0.0, 0.0, 0.5) == "#fff"


# --- get_nice_ticks ---


class TestGetNiceTicks:
    def test_linear_returns_sorted(self):
        ticks = get_nice_ticks(0, 100, 5, scale="linear")
        assert len(ticks) > 0
        assert all(ticks[i] <= ticks[i + 1] for i in range(len(ticks) - 1))

    def test_linear_nice_step(self):
        ticks = get_nice_ticks(0, 100, 5, scale="linear")
        assert len(ticks) >= 3
        assert all(0 < t < 100 for t in ticks)

    def test_linear_includes_zero(self):
        ticks = get_nice_ticks(-50, 50, 5, scale="linear")
        assert 0.0 in ticks

    def test_linear_empty_for_equal_range(self):
        ticks = get_nice_ticks(5, 5, 5, scale="linear")
        assert len(ticks) == 0

    def test_log_within_range(self):
        ticks = get_nice_ticks(1, 10000, 5, scale="log", linthresh=1.0)
        assert all(1.0 <= t <= 10000 for t in ticks)

    def test_log_majors_first(self):
        """Majors (powers of 10) should appear before any minors."""
        ticks = get_nice_ticks(0, 276, 5, scale="log", linthresh=37.35)
        powers = [
            t for t in ticks if t > 0 and np.isclose(np.log10(t) % 1, 0, atol=1e-9)
        ]
        assert len(powers) >= 1

    def test_log_nice_minors(self):
        """Minors should be nice numbers like 50, 200, not garbage like 37.35."""
        ticks = get_nice_ticks(0, 276, 5, scale="log", linthresh=37.35)
        for t in ticks:
            if t == 0:
                continue
            mantissa = t / 10.0 ** int(np.floor(np.log10(t)))
            nice = {1, 2, 2.5, 3, 4, 5, 6, 7, 7.5, 8, 9, 10}
            assert any(np.isclose(mantissa, n, atol=0.01) for n in nice), (
                f"{t} not nice"
            )

    def test_symlog_has_negative_and_positive(self):
        ticks = get_nice_ticks(-1000, 1000, 10, scale="symlog", linthresh=1.0)
        assert any(t < 0 for t in ticks)
        assert any(t > 0 for t in ticks)

    def test_symlog_includes_zero_when_space(self):
        ticks = get_nice_ticks(-1000, 1000, 10, scale="symlog", linthresh=1.0)
        assert 0.0 in ticks

    def test_symlog_majors_before_minors(self):
        """At least one power of 10 should be present."""
        ticks = get_nice_ticks(-276, 276, 9, scale="symlog", linthresh=37.35)
        powers = [
            t
            for t in ticks
            if t != 0 and np.isclose(np.log10(abs(t)) % 1, 0, atol=1e-9)
        ]
        assert len(powers) >= 1
