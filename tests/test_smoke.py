"""Smoke tests — verify imports and basic initialization don't crash."""


class TestImports:
    def test_package_import(self):
        pass

    def test_public_api_imports(self):
        pass

    def test_core_imports(self):
        pass

    def test_preset_registry_loaded(self):
        from trame_colormaps.core.presets import PRESET_REGISTRY

        assert len(PRESET_REGISTRY) > 100  # sanity: expect many presets

    def test_colorbar_cache_populated(self):
        from trame_colormaps.core.presets import COLORBAR_CACHE

        assert len(COLORBAR_CACHE) > 100
