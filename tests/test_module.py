"""Tests for trame_colormaps.module."""

from trame_colormaps import module


class TestModuleSetup:
    def test_setup_exists(self):
        assert hasattr(module, "setup")

    def test_setup_callable(self):
        assert callable(module.setup)

    def test_setup_noop(self):
        """setup() should accept app + kwargs and do nothing."""
        module.setup(None)
        module.setup(None, foo="bar")
