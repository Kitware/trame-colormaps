"""Smoke tests — verify imports and basic initialization don't crash."""


class TestImports:
    def test_package_import(self):
        import trame_colormaps  # noqa: F401

    def test_trame_dataclasses_entry_point(self):
        from trame.dataclasses import colormaps

        assert hasattr(colormaps, "ColormapConfig")

    def test_trame_dataclasses_reexport(self):
        from trame.dataclasses.colormaps import ColormapConfig
        from trame_colormaps.dataclasses import ColormapConfig as Direct

        assert ColormapConfig is Direct

    def test_trame_widgets_entry_point(self):
        from trame.widgets import colormaps

        assert hasattr(colormaps, "HorizontalScalarBar")
        assert hasattr(colormaps, "VerticalScalarBar")
        assert hasattr(colormaps, "ColorMapEditor")

    def test_trame_widgets_initialize(self):
        from trame.widgets.colormaps import initialize

        assert callable(initialize)

    def test_core_imports(self):
        from trame_colormaps.core import presets, ticks, transforms  # noqa: F401

    def test_preset_registry_loaded(self):
        from trame_colormaps.core.presets import PRESET_REGISTRY

        assert len(PRESET_REGISTRY) > 100  # sanity: expect many presets

    def test_colorbar_cache_populated(self):
        from trame_colormaps.core.presets import COLORBAR_CACHE

        assert len(COLORBAR_CACHE) > 100
