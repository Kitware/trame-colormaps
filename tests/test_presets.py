"""Tests for trame_colormaps.core.presets."""

import pytest
from vtkmodules.vtkRenderingCore import vtkColorTransferFunction

from trame_colormaps.core.presets import (
    ALL_PRESETS,
    COLOR_BLIND_SAFE,
    COLORBAR_CACHE,
    DEFAULT_PRESETS,
    PRESET_REGISTRY,
    apply_preset,
    get_active_presets,
    get_cached_colorbar_image,
    get_preset_ctf,
    get_preset_metadata,
    get_rgb_points,
    invert_ctf,
    lut_to_img_h,
    lut_to_img_v,
    map_to_log_space,
    rescale_ctf,
    set_active_presets,
    set_rgb_points,
)

# --- Registry ---


class TestRegistry:
    def test_registry_not_empty(self):
        assert len(PRESET_REGISTRY) > 0

    def test_all_presets_matches_registry(self):
        assert ALL_PRESETS == set(PRESET_REGISTRY.keys())

    def test_default_presets_subset_of_registry(self):
        for name in DEFAULT_PRESETS:
            assert name in PRESET_REGISTRY

    def test_color_blind_safe_subset(self):
        assert COLOR_BLIND_SAFE <= ALL_PRESETS

    def test_known_preset_exists(self):
        assert "Cool to Warm" in PRESET_REGISTRY
        assert "batlow" in PRESET_REGISTRY

    def test_preset_has_rgb_points(self):
        for name, preset in PRESET_REGISTRY.items():
            assert "RGBPoints" in preset, f"{name} missing RGBPoints"
            assert len(preset["RGBPoints"]) >= 8, f"{name} has too few points"


# --- Active Presets ---


class TestActivePresets:
    def test_get_returns_list(self):
        result = get_active_presets()
        assert isinstance(result, list)

    def test_set_and_get_roundtrip(self):
        original = get_active_presets()
        try:
            set_active_presets(["Cool to Warm", "batlow"])
            result = get_active_presets()
            assert result == ["Cool to Warm", "batlow"]
        finally:
            set_active_presets(original)

    def test_set_ignores_unknown(self):
        original = get_active_presets()
        try:
            set_active_presets(["Cool to Warm", "NONEXISTENT_PRESET"])
            result = get_active_presets()
            assert result == ["Cool to Warm"]
        finally:
            set_active_presets(original)


# --- COLORBAR_CACHE ---


class TestColorbarCache:
    def test_cache_has_entries(self):
        assert len(COLORBAR_CACHE) > 0

    def test_cache_keys_match_registry(self):
        assert set(COLORBAR_CACHE.keys()) == set(PRESET_REGISTRY.keys())

    def test_cache_has_normal_and_inverted(self):
        for name, entry in COLORBAR_CACHE.items():
            assert "normal" in entry, f"{name} missing normal"
            assert "inverted" in entry, f"{name} missing inverted"

    def test_cache_images_are_data_uris(self):
        entry = COLORBAR_CACHE["Cool to Warm"]
        assert entry["normal"].startswith("data:image/png;base64,")
        assert entry["inverted"].startswith("data:image/png;base64,")


# --- get_cached_colorbar_image ---


class TestGetCachedColorbarImage:
    def test_normal(self):
        img = get_cached_colorbar_image("Cool to Warm")
        assert img.startswith("data:image/png;base64,")

    def test_inverted(self):
        img = get_cached_colorbar_image("Cool to Warm", inverted=True)
        assert img.startswith("data:image/png;base64,")

    def test_unknown_returns_empty(self):
        assert get_cached_colorbar_image("NONEXISTENT") == ""


# --- get_preset_ctf ---


class TestGetPresetCtf:
    def test_returns_ctf(self):
        ctf = get_preset_ctf("Cool to Warm")
        assert isinstance(ctf, vtkColorTransferFunction)
        assert ctf.GetSize() > 0

    def test_unknown_returns_none(self):
        assert get_preset_ctf("NONEXISTENT") is None


# --- get_preset_metadata ---


class TestGetPresetMetadata:
    def test_returns_dict(self):
        meta = get_preset_metadata("Cool to Warm")
        assert isinstance(meta, dict)
        assert "Name" not in meta or meta["Name"] == "Cool to Warm"

    def test_excludes_rgb_points(self):
        meta = get_preset_metadata("Cool to Warm")
        assert "RGBPoints" not in meta

    def test_unknown_returns_none(self):
        assert get_preset_metadata("NONEXISTENT") is None


# --- CTF Helpers ---


class TestCtfHelpers:
    def test_get_set_rgb_points_roundtrip(self):
        ctf = vtkColorTransferFunction()
        ctf.AddRGBPoint(0.0, 1.0, 0.0, 0.0)
        ctf.AddRGBPoint(1.0, 0.0, 0.0, 1.0)
        pts = get_rgb_points(ctf)
        assert len(pts) == 8

        ctf2 = vtkColorTransferFunction()
        set_rgb_points(ctf2, pts)
        pts2 = get_rgb_points(ctf2)
        assert pts == pytest.approx(pts2)

    def test_apply_preset(self):
        ctf = vtkColorTransferFunction()
        apply_preset(ctf, "Cool to Warm")
        assert ctf.GetSize() > 0

    def test_apply_preset_unknown_noop(self):
        ctf = vtkColorTransferFunction()
        ctf.AddRGBPoint(0, 1, 0, 0)
        size_before = ctf.GetSize()
        apply_preset(ctf, "NONEXISTENT")
        assert ctf.GetSize() == size_before

    def test_invert_ctf(self):
        ctf = vtkColorTransferFunction()
        apply_preset(ctf, "Cool to Warm")
        pts_before = get_rgb_points(ctf)
        invert_ctf(ctf)
        pts_after = get_rgb_points(ctf)
        assert pts_before != pts_after
        # Inverting twice should restore original
        invert_ctf(ctf)
        pts_restored = get_rgb_points(ctf)
        assert pts_before == pytest.approx(pts_restored, abs=1e-6)

    def test_rescale_ctf(self):
        ctf = vtkColorTransferFunction()
        apply_preset(ctf, "Cool to Warm")
        rescale_ctf(ctf, 10.0, 20.0)
        r = ctf.GetRange()
        assert r[0] == pytest.approx(10.0)
        assert r[1] == pytest.approx(20.0)

    def test_lut_to_img_h(self):
        ctf = vtkColorTransferFunction()
        apply_preset(ctf, "Cool to Warm")
        img = lut_to_img_h(ctf)
        assert img.startswith("data:image/png;base64,")

    def test_lut_to_img_v(self):
        ctf = vtkColorTransferFunction()
        apply_preset(ctf, "Cool to Warm")
        img = lut_to_img_v(ctf)
        assert img.startswith("data:image/png;base64,")

    def test_map_to_log_space(self):
        ctf = vtkColorTransferFunction()
        apply_preset(ctf, "Cool to Warm")
        rescale_ctf(ctf, 1.0, 1000.0)
        pts_before = get_rgb_points(ctf)
        map_to_log_space(ctf)
        pts_after = get_rgb_points(ctf)
        # After log mapping, intermediate x values should shift
        # (endpoints might stay the same, so check an interior point)
        assert len(pts_before) == len(pts_after)
        if len(pts_before) > 8:
            # Compare a mid-point x value
            mid = len(pts_before) // 2
            mid_idx = (mid // 4) * 4  # align to 4-tuple boundary
            assert pts_before[mid_idx] != pytest.approx(pts_after[mid_idx], rel=0.01)
