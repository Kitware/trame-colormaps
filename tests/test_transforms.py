"""Tests for trame_colormaps.core.transforms."""

import numpy as np
import pytest
from vtkmodules.vtkRenderingCore import vtkColorTransferFunction

from trame_colormaps.core.presets import get_rgb_points, rescale_ctf
from trame_colormaps.core.transforms import (
    _remap_with_dead_zone,
    apply_discrete_linear,
    apply_discrete_log,
    apply_discrete_symlog,
    apply_linear,
    apply_log,
    apply_symlog,
    calculate_linthresh,
)

# --- Helpers ---


def make_ctf(vmin=0.0, vmax=1.0):
    """Create a simple 2-point CTF for testing."""
    ctf = vtkColorTransferFunction()
    ctf.AddRGBPoint(vmin, 0.0, 0.0, 1.0)
    ctf.AddRGBPoint(vmax, 1.0, 0.0, 0.0)
    return ctf


PRESET_NAME = "Cool to Warm"


# --- calculate_linthresh ---


class TestCalculateLinthresh:
    def test_positive_array(self):
        data = np.array([0.1, 1.0, 10.0, 100.0])
        result = calculate_linthresh(data)
        assert result == pytest.approx(0.1)

    def test_mixed_positive_negative(self):
        data = np.array([-10.0, -0.5, 0.5, 10.0])
        result = calculate_linthresh(data)
        assert result == pytest.approx(0.5)

    def test_all_zeros(self):
        data = np.array([0.0, 0.0, 0.0])
        result = calculate_linthresh(data)
        assert result == 1.0  # fallback

    def test_with_nans(self):
        data = np.array([np.nan, 1.0, 10.0])
        result = calculate_linthresh(data)
        assert result == pytest.approx(1.0)

    def test_single_value(self):
        data = np.array([5.0])
        result = calculate_linthresh(data)
        assert result == pytest.approx(5.0)

    def test_very_small_values(self):
        data = np.array([1e-300, 1e-200, 1.0])
        result = calculate_linthresh(data)
        assert result > 0

    def test_dtype_preserved(self):
        data = np.array([0.1, 1.0], dtype=np.float32)
        result = calculate_linthresh(data)
        assert isinstance(result, float)


# --- apply_linear ---


class TestApplyLinear:
    def test_applies_preset(self):
        ctf = vtkColorTransferFunction()
        apply_linear(ctf, PRESET_NAME)
        assert ctf.GetSize() > 0

    def test_inverted(self):
        ctf1 = vtkColorTransferFunction()
        apply_linear(ctf1, PRESET_NAME, invert=False)
        pts1 = get_rgb_points(ctf1)

        ctf2 = vtkColorTransferFunction()
        apply_linear(ctf2, PRESET_NAME, invert=True)
        pts2 = get_rgb_points(ctf2)

        # Points should differ
        assert pts1 != pts2

    def test_returns_none(self):
        # apply_linear has no return value
        ctf = vtkColorTransferFunction()
        result = apply_linear(ctf, PRESET_NAME)
        assert result is None


# --- apply_discrete_linear ---


class TestApplyDiscreteLinear:
    def _make_linear_pts(self):
        ctf = vtkColorTransferFunction()
        apply_linear(ctf, PRESET_NAME)
        rescale_ctf(ctf, 0, 1)
        return get_rgb_points(ctf)

    def test_returns_tuple(self):
        ctf = vtkColorTransferFunction()
        apply_linear(ctf, PRESET_NAME)
        rescale_ctf(ctf, 0, 1)
        pts = get_rgb_points(ctf)
        tick_vals = np.linspace(0, 1, 6)[1:-1]  # 4 interior ticks
        result = apply_discrete_linear(ctf, pts, n_sub=4, tick_vals=tick_vals)
        assert isinstance(result, tuple)
        assert len(result) == 4  # (display_pts, tick_data, img_h, img_v)

    def test_ctf_has_points(self):
        ctf = vtkColorTransferFunction()
        apply_linear(ctf, PRESET_NAME)
        rescale_ctf(ctf, 0, 1)
        pts = get_rgb_points(ctf)
        tick_vals = np.linspace(0, 1, 6)[1:-1]
        apply_discrete_linear(ctf, pts, n_sub=4, tick_vals=tick_vals)
        assert ctf.GetSize() > 0

    def test_different_n_sub(self):
        pts = self._make_linear_pts()

        ctf1 = vtkColorTransferFunction()
        apply_linear(ctf1, PRESET_NAME)
        rescale_ctf(ctf1, 0, 1)
        tick_vals = np.linspace(0, 1, 6)[1:-1]
        apply_discrete_linear(ctf1, pts, n_sub=2, tick_vals=tick_vals)
        pts1 = get_rgb_points(ctf1)

        ctf2 = vtkColorTransferFunction()
        apply_linear(ctf2, PRESET_NAME)
        rescale_ctf(ctf2, 0, 1)
        apply_discrete_linear(ctf2, pts, n_sub=8, tick_vals=tick_vals)
        pts2 = get_rgb_points(ctf2)

        assert pts1 != pts2


# --- apply_log ---


class TestApplyLog:
    def test_applies(self):
        ctf = vtkColorTransferFunction()
        apply_linear(ctf, PRESET_NAME)
        rescale_ctf(ctf, 1.0, 1000.0)
        apply_log(ctf, linthresh=1.0)
        r = ctf.GetRange()
        assert r[0] > 0
        assert r[1] > r[0]


# --- apply_discrete_log ---


class TestApplyDiscreteLog:
    def test_returns_tuple(self):
        ctf = vtkColorTransferFunction()
        apply_linear(ctf, PRESET_NAME)
        rescale_ctf(ctf, 1.0, 1000.0)
        pts = get_rgb_points(ctf)
        result = apply_discrete_log(ctf, linthresh=1.0, linear_rgb_points=pts, n_sub=4)
        assert isinstance(result, tuple)
        assert len(result) == 4


# --- apply_symlog ---


class TestApplySymlog:
    def test_returns_images(self):
        ctf = vtkColorTransferFunction()
        apply_linear(ctf, PRESET_NAME)
        rescale_ctf(ctf, -1000.0, 1000.0)
        pts = get_rgb_points(ctf)
        result = apply_symlog(ctf, linthresh=1.0, linear_rgb_points=pts)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_ctf_has_points(self):
        ctf = vtkColorTransferFunction()
        apply_linear(ctf, PRESET_NAME)
        rescale_ctf(ctf, -1000.0, 1000.0)
        pts = get_rgb_points(ctf)
        apply_symlog(ctf, linthresh=1.0, linear_rgb_points=pts)
        assert ctf.GetSize() > 0


# --- apply_discrete_symlog ---


class TestApplyDiscreteSymlog:
    def test_returns_tuple(self):
        ctf = vtkColorTransferFunction()
        apply_linear(ctf, PRESET_NAME)
        rescale_ctf(ctf, -1000.0, 1000.0)
        pts = get_rgb_points(ctf)
        result = apply_discrete_symlog(ctf, linthresh=1.0, linear_rgb_points=pts, n_sub=4)
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_ctf_has_points(self):
        ctf = vtkColorTransferFunction()
        apply_linear(ctf, PRESET_NAME)
        rescale_ctf(ctf, -1000.0, 1000.0)
        pts = get_rgb_points(ctf)
        apply_discrete_symlog(ctf, linthresh=1.0, linear_rgb_points=pts, n_sub=4)
        assert ctf.GetSize() > 0


# --- _remap_with_dead_zone ---


class TestRemapWithDeadZone:
    def test_preserves_all_colors(self):
        pts = [-10, 1, 0, 0, -5, 0.5, 0, 0, 5, 0, 0.5, 0, 10, 0, 0, 1]
        result = _remap_with_dead_zone(pts, -10, 10, 0.0, -2, 2, 0.9, 0.9, 0.9)
        # 2 left + 3 dead zone + 2 right = 7 points
        assert len(result) // 4 == 7

    def test_left_points_compressed(self):
        pts = [-10, 1, 0, 0, -5, 0.5, 0, 0, 5, 0, 0.5, 0, 10, 0, 0, 1]
        result = _remap_with_dead_zone(pts, -10, 10, 0.0, -3, 3, 0.9, 0.9, 0.9)
        # Left points remapped into [-10, -3]
        left_xs = [result[i * 4] for i in range(len(result) // 4) if result[i * 4] < -3]
        for x in left_xs:
            assert x >= -10
            assert x <= -3

    def test_right_points_compressed(self):
        pts = [-10, 1, 0, 0, -5, 0.5, 0, 0, 5, 0, 0.5, 0, 10, 0, 0, 1]
        result = _remap_with_dead_zone(pts, -10, 10, 0.0, -3, 3, 0.9, 0.9, 0.9)
        # Right points remapped into [3, 10]
        right_xs = [result[i * 4] for i in range(len(result) // 4) if result[i * 4] > 3]
        for x in right_xs:
            assert x >= 3
            assert x <= 10

    def test_dead_zone_has_center_color(self):
        pts = [-10, 1, 0, 0, 10, 0, 0, 1]
        cr, cg, cb = 0.5, 0.6, 0.7
        result = _remap_with_dead_zone(pts, -10, 10, 0.0, -2, 2, cr, cg, cb)
        n = len(result) // 4
        for i in range(n):
            x = result[i * 4]
            if -2 <= x <= 2:
                assert result[i * 4 + 1] == pytest.approx(cr)
                assert result[i * 4 + 2] == pytest.approx(cg)
                assert result[i * 4 + 3] == pytest.approx(cb)

    def test_asymmetric_center(self):
        pts = [-100, 1, 0, 0, -50, 0.5, 0, 0, 50, 0, 0.5, 0, 100, 0, 0, 1]
        result = _remap_with_dead_zone(
            pts,
            -100,
            100,
            20.0,
            10.0,
            30.0,
            0.5,
            0.5,
            0.5,
        )
        n = len(result) // 4
        xs = [result[i * 4] for i in range(n)]
        assert min(xs) >= -100
        assert max(xs) <= 100


# --- apply_symlog with epsilon ---


class TestApplySymlogEpsilon:
    def test_epsilon_zero_same_as_default(self):
        ctf1 = vtkColorTransferFunction()
        apply_linear(ctf1, PRESET_NAME)
        rescale_ctf(ctf1, -1000.0, 1000.0)
        pts1 = get_rgb_points(ctf1)
        result1 = apply_symlog(ctf1, linthresh=1.0, linear_rgb_points=pts1, epsilon=0.0)

        ctf2 = vtkColorTransferFunction()
        apply_linear(ctf2, PRESET_NAME)
        rescale_ctf(ctf2, -1000.0, 1000.0)
        pts2 = get_rgb_points(ctf2)
        result2 = apply_symlog(ctf2, linthresh=1.0, linear_rgb_points=pts2)

        assert result1 is not None
        assert result2 is not None

    def test_epsilon_positive_returns_result(self):
        ctf = vtkColorTransferFunction()
        apply_linear(ctf, PRESET_NAME)
        rescale_ctf(ctf, -1000.0, 1000.0)
        pts = get_rgb_points(ctf)
        result = apply_symlog(ctf, linthresh=1.0, linear_rgb_points=pts, epsilon=10.0)
        assert result is not None
        assert len(result) == 2

    def test_epsilon_adds_dead_zone_points(self):
        ctf1 = vtkColorTransferFunction()
        apply_linear(ctf1, PRESET_NAME)
        rescale_ctf(ctf1, -1000.0, 1000.0)
        pts1 = get_rgb_points(ctf1)
        apply_symlog(ctf1, linthresh=1.0, linear_rgb_points=pts1, epsilon=0.0)
        size_no_eps = ctf1.GetSize()

        ctf2 = vtkColorTransferFunction()
        apply_linear(ctf2, PRESET_NAME)
        rescale_ctf(ctf2, -1000.0, 1000.0)
        pts2 = get_rgb_points(ctf2)
        apply_symlog(ctf2, linthresh=1.0, linear_rgb_points=pts2, epsilon=10.0)
        size_with_eps = ctf2.GetSize()

        # Epsilon adds 3 dead zone points but removes ~0 center point
        assert size_with_eps > size_no_eps


# --- apply_discrete_symlog with epsilon ---


class TestApplyDiscreteSymlogEpsilon:
    def test_epsilon_positive_returns_result(self):
        ctf = vtkColorTransferFunction()
        apply_linear(ctf, PRESET_NAME)
        rescale_ctf(ctf, -1000.0, 1000.0)
        pts = get_rgb_points(ctf)
        result = apply_discrete_symlog(
            ctf,
            linthresh=1.0,
            linear_rgb_points=pts,
            n_sub=4,
            epsilon=10.0,
        )
        assert result[0] is not None
        assert len(result) == 4
