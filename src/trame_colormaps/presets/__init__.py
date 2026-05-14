"""Bundled colormap preset JSON files.

These are loaded by core/presets.py at import time. This package exists
solely to ship the JSON data files with the Python package.

Sources and processing scripts:

- paraview_colormaps.json
  Source: https://gitlab.kitware.com/paraview/paraview/-/raw/master/Remoting/Views/ColorMaps.json
  License: BSD-3-Clause (Kitware Inc. and ParaView contributors)
  Script: docs/scripts/fetch_paraview_presets.py

- crameri_colormaps.json
  Source: https://www.fabiocrameri.ch/colourmaps/
  Author: Fabio Crameri — Crameri, F. (2018). Scientific colour maps. Zenodo.
  License: MIT
  Processing: 0–255 integer RGB → 0–1 float, linearly spaced x values
  Script: docs/scripts/fetch_crameri_presets.py

- default_presets.json
  Curated default subset used by this library.
"""
