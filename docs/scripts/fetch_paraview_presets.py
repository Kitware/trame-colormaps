#!/usr/bin/env python3
"""Fetch and process ParaView color presets into our bundled JSON format.

Source
------
ParaView ColorMaps.json from the official GitLab repository:
    https://gitlab.kitware.com/paraview/paraview/-/raw/master/Remoting/Views/ColorMaps.json

License: BSD-3-Clause
Authors: Kitware Inc. and ParaView contributors

Processing
----------
The source file contains presets with RGBPoints already in [x, r, g, b, ...]
format with values in the 0–1 range.  This script:

1. Downloads the source JSON from ParaView's GitLab.
2. Keeps only presets with "RGBPoints" (skips opacity-only or indexed presets).
3. Preserves metadata: Name, ColorSpace, NanColor, Creator, DefaultMap.
4. Adds Source and License fields to every preset.
5. Marks known color-blind safe presets.
6. Writes the result to paraview_colormaps.json.

Usage
-----
    python docs/scripts/fetch_paraview_presets.py

Output is written to:
    src/trame_colormaps/presets/paraview_colormaps.json
"""

import json
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://gitlab.kitware.com/paraview/paraview/"
    "-/raw/master/Remoting/Views/ColorMaps.json"
)
SOURCE_LICENSE = "BSD-3-Clause"

# Presets known to be color-blind safe.  Add names here as needed.
COLOR_BLIND_SAFE = {
    "Cool to Warm",
    "Inferno (matplotlib)",
    "Viridis (matplotlib)",
    "Plasma (matplotlib)",
    "Cividis",
}

OUTPUT = Path(__file__).resolve().parents[2] / "src" / "trame_colormaps" / "presets" / "paraview_colormaps.json"


def main():
    print(f"Downloading from {SOURCE_URL} ...")
    with urllib.request.urlopen(SOURCE_URL) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    print(f"  Fetched {len(raw)} entries")

    presets = []
    for entry in raw:
        if "RGBPoints" not in entry:
            continue

        preset = {}
        # Carry over standard fields
        for key in ("ColorSpace", "Name", "NanColor", "DefaultMap", "Creator", "RGBPoints"):
            if key in entry:
                preset[key] = entry[key]

        preset["ColorBlindSafe"] = entry.get("Name", "") in COLOR_BLIND_SAFE
        preset["Source"] = SOURCE_URL
        preset["License"] = SOURCE_LICENSE

        presets.append(preset)

    print(f"  Kept {len(presets)} presets with RGBPoints")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(presets, indent=2) + "\n")
    print(f"  Written to {OUTPUT}")


if __name__ == "__main__":
    main()
