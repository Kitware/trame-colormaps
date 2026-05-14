#!/usr/bin/env python3
"""Fetch and process Fabio Crameri's scientific colour maps into our bundled JSON format.

Source
------
Scientific colour maps by Fabio Crameri:
    https://www.fabiocrameri.ch/colourmaps/

Download page (ZIP archive of .txt files with 0–255 RGB values):
    https://zenodo.org/records/8409685

License: MIT
Author:  Fabio Crameri

Citation:
    Crameri, F. (2018). Scientific colour maps. Zenodo.
    https://doi.org/10.5281/zenodo.1243862

Processing
----------
Crameri distributes colour maps as plain-text files, each with 256 rows
of space-separated R G B values in the 0–255 integer range.  This script:

1. Downloads the latest ZIP archive from Zenodo.
2. Extracts each colourmap's .txt file (e.g. batlow/batlow.txt).
3. Converts RGB values from 0–255 integers to 0–1 floats (val / 255).
4. Builds RGBPoints as [x, r, g, b, ...] with x linearly spaced 0–1.
5. Adds metadata: Name, Creator, Source, License, Category, ColorBlindSafe.
6. Writes the result to crameri_colormaps.json.

Usage
-----
    python docs/scripts/fetch_crameri_presets.py

Output is written to:
    src/trame_colormaps/presets/crameri_colormaps.json
"""

import io
import json
import zipfile
import urllib.request
from pathlib import Path

# Latest stable release on Zenodo.  Update the record ID for newer versions.
SOURCE_URL = "https://zenodo.org/records/8409685/files/ScientificColourMaps8.zip"
SOURCE_PAGE = "https://www.fabiocrameri.ch/colourmaps/"
SOURCE_LICENSE = "MIT"
SOURCE_CREATOR = "Fabio Crameri"

# Category and color-blind safety metadata per colourmap.
# Reference: https://www.fabiocrameri.ch/ws/media-library/ce2eb6eee7c345f999e61c02e2733962/readme_scientificcolourmaps.pdf
METADATA = {
    # Sequential
    "batlow":   {"category": "sequential", "safe": True},
    "batlowW":  {"category": "sequential", "safe": True},
    "batlowK":  {"category": "sequential", "safe": True},
    "devon":    {"category": "sequential", "safe": True},
    "lajolla":  {"category": "sequential", "safe": True},
    "bamako":   {"category": "sequential", "safe": True},
    "davos":    {"category": "sequential", "safe": True},
    "bilbao":   {"category": "sequential", "safe": True},
    "nuuk":     {"category": "sequential", "safe": True},
    "oslo":     {"category": "sequential", "safe": True},
    "grayC":    {"category": "sequential", "safe": True},
    "hawaii":   {"category": "sequential", "safe": True},
    "lapaz":    {"category": "sequential", "safe": True},
    "tokyo":    {"category": "sequential", "safe": True},
    "buda":     {"category": "sequential", "safe": True},
    "acton":    {"category": "sequential", "safe": True},
    "turku":    {"category": "sequential", "safe": True},
    "imola":    {"category": "sequential", "safe": True},
    "navia":    {"category": "sequential", "safe": True},
    "naviaW":   {"category": "sequential", "safe": True},
    "managua":  {"category": "sequential", "safe": True},
    "bukavu":   {"category": "multi-sequential", "safe": True},
    "fes":      {"category": "multi-sequential", "safe": True},
    # Diverging
    "broc":     {"category": "diverging", "safe": True},
    "brocO":    {"category": "diverging", "safe": True},
    "cork":     {"category": "diverging", "safe": True},
    "corkO":    {"category": "diverging", "safe": True},
    "vik":      {"category": "diverging", "safe": True},
    "vikO":     {"category": "diverging", "safe": True},
    "lisbon":   {"category": "diverging", "safe": True},
    "tofino":   {"category": "diverging", "safe": True},
    "berlin":   {"category": "diverging", "safe": True},
    "roma":     {"category": "diverging", "safe": True},
    "romaO":    {"category": "diverging", "safe": True},
    "bam":      {"category": "diverging", "safe": True},
    "bamO":     {"category": "diverging", "safe": True},
    "vanimo":   {"category": "diverging", "safe": True},
    # Cyclic
    "oleron":   {"category": "cyclic", "safe": True},
    "brocO":    {"category": "cyclic", "safe": True},
    "corkO":    {"category": "cyclic", "safe": True},
    "vikO":     {"category": "cyclic", "safe": True},
    "romaO":    {"category": "cyclic", "safe": True},
    "bamO":     {"category": "cyclic", "safe": True},
    # Categorical
    "glasgowS": {"category": "categorical", "safe": True},
}

OUTPUT = Path(__file__).resolve().parents[2] / "src" / "trame_colormaps" / "presets" / "crameri_colormaps.json"


def parse_txt(text):
    """Parse a Crameri .txt file: 256 rows of 'R G B' (0–255) → 0–1 floats."""
    rgb_points = []
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    n = len(lines)
    for i, line in enumerate(lines):
        parts = line.split()
        r = round(float(parts[0]) / 255.0, 6)
        g = round(float(parts[1]) / 255.0, 6)
        b = round(float(parts[2]) / 255.0, 6)
        x = round(i / (n - 1), 6) if n > 1 else 0.0
        rgb_points.extend([x, r, g, b])
    return rgb_points


def main():
    print(f"Downloading from {SOURCE_URL} ...")
    with urllib.request.urlopen(SOURCE_URL) as resp:
        zip_data = io.BytesIO(resp.read())

    presets = []
    with zipfile.ZipFile(zip_data) as zf:
        # Look for files like ScientificColourMaps8/batlow/batlow.txt
        txt_files = sorted(
            n for n in zf.namelist()
            if n.endswith(".txt")
            and n.count("/") == 2  # top/name/name.txt
            and not n.startswith("__")
        )
        print(f"  Found {len(txt_files)} .txt colourmap files")

        for path in txt_files:
            name = Path(path).stem
            text = zf.read(path).decode("utf-8")
            rgb_points = parse_txt(text)

            meta = METADATA.get(name, {})
            preset = {
                "ColorSpace": "RGB",
                "Name": name,
                "Creator": SOURCE_CREATOR,
                "Source": SOURCE_PAGE,
                "License": SOURCE_LICENSE,
                "Category": meta.get("category", "sequential"),
                "ColorBlindSafe": meta.get("safe", False),
                "RGBPoints": rgb_points,
            }
            presets.append(preset)

    print(f"  Processed {len(presets)} presets")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(presets, indent=2) + "\n")
    print(f"  Written to {OUTPUT}")


if __name__ == "__main__":
    main()
