"""Generate docs/colormaps.md with colorbar images saved as PNG files.

Run from repo root:
    uv run python docs/scripts/generate_colormaps_md.py
"""

import json
from pathlib import Path

from vtkmodules.vtkCommonCore import vtkUnsignedCharArray
from vtkmodules.vtkCommonDataModel import vtkImageData
from vtkmodules.vtkIOImage import vtkPNGWriter
from vtkmodules.vtkRenderingCore import vtkColorTransferFunction

REPO_ROOT = Path(__file__).parent.parent.parent
PRESET_DIR = REPO_ROOT / "src" / "trame_colormaps" / "presets"
IMG_DIR = REPO_ROOT / "docs" / "images" / "colormaps"


def build_ctf(preset):
    ctf = vtkColorTransferFunction()
    cs = preset.get("ColorSpace", "RGB")
    if cs == "Diverging":
        ctf.SetColorSpaceToDiverging()
    elif cs == "HSV":
        ctf.SetColorSpaceToHSV()
    elif cs == "Lab":
        ctf.SetColorSpaceToLab()
    else:
        ctf.SetColorSpaceToRGB()
    pts = preset["RGBPoints"]
    for i in range(0, len(pts), 4):
        ctf.AddRGBPoint(pts[i], pts[i + 1], pts[i + 2], pts[i + 3])
    return ctf


def ctf_to_png_file(ctf, filepath, width=512, height=40):
    """Render a color transfer function to a PNG file."""
    rgb = [0.0, 0.0, 0.0]
    ca = vtkUnsignedCharArray()
    ca.SetNumberOfComponents(3)
    ca.SetNumberOfTuples(width * height)
    img = vtkImageData()
    img.SetDimensions(width, height, 1)
    img.GetPointData().SetScalars(ca)

    vmin, vmax = ctf.GetRange()
    step = (vmax - vmin) / (width - 1) if width > 1 else 0

    for col in range(width):
        v = vmin + step * col
        ctf.GetColor(v, rgb)
        r = int(round(rgb[0] * 255))
        g = int(round(rgb[1] * 255))
        b = int(round(rgb[2] * 255))
        for row in range(height):
            ca.SetTuple3(row * width + col, r, g, b)

    w = vtkPNGWriter()
    w.SetFileName(str(filepath))
    w.SetInputData(img)
    w.SetCompressionLevel(5)
    w.Write()


def safe_filename(name):
    """Convert preset name to a safe filename."""
    return name.replace(" ", "_").replace("/", "-").replace("(", "").replace(")", "").replace("'", "")


def main():
    IMG_DIR.mkdir(exist_ok=True)

    pv = json.loads((PRESET_DIR / "paraview_colormaps.json").read_text())
    cr = json.loads((PRESET_DIR / "crameri_colormaps.json").read_text())

    lines = [
        "# Colormaps Reference",
        "",
        "Complete catalog of available colormaps with colorbar previews and metadata.",
        "",
        f"**Total: {len(pv) + len(cr)} colormaps** ({len(pv)} ParaView built-in + {len(cr)} Crameri scientific)",
        "",
        "## ParaView Built-in Colormaps",
        "",
        f"{len(pv)} colormaps from the [ParaView](https://github.com/Kitware/ParaView/blob/master/Remoting/Views/ColorMaps.json) project.",
        "",
    ]

    for p in sorted(pv, key=lambda x: (x.get("ColorSpace", "RGB"), x.get("Creator", ""), x["Name"].lower())):
        fname = safe_filename(p["Name"]) + ".png"
        ctf = build_ctf(p)
        ctf_to_png_file(ctf, IMG_DIR / fname)
        creator = p.get("Creator", "")
        cs = p.get("ColorSpace", "RGB")
        meta = f'**{p["Name"]}** — {cs}'
        if creator:
            meta += f' — {creator}'
        lines.append(f'{meta}')
        lines.append(f'')
        lines.append(f'<img src="images/colormaps/{fname}" width="500">')
        lines.append(f'')

    lines += [
        "",
        "## Crameri Scientific Colour Maps",
        "",
        f'{len(cr)} colormaps from [Fabio Crameri](https://www.fabiocrameri.ch/colourmaps/) — perceptually uniform and color-blind safe.',
        "",
    ]

    for p in sorted(cr, key=lambda x: (x.get("Category", ""), x["Name"].lower())):
        fname = safe_filename(p["Name"]) + ".png"
        ctf = build_ctf(p)
        ctf_to_png_file(ctf, IMG_DIR / fname)
        cat = p.get("Category", "")
        cs = p.get("ColorSpace", "RGB")
        meta = f'**{p["Name"]}** — {cs} — {cat}'
        lines.append(f'{meta}')
        lines.append(f'')
        lines.append(f'<img src="images/colormaps/{fname}" width="500">')
        lines.append(f'')

    lines += [
        "",
        "---",
        "",
        "*Generated from `paraview_colormaps.json` and `crameri_colormaps.json`.*",
    ]

    out = REPO_ROOT / "docs" / "colormaps.md"
    out.write_text("\n".join(lines))
    print(f"Written {out.relative_to(REPO_ROOT)} ({len(lines)} lines, {len(pv) + len(cr)} images in docs/images/colormaps/)")


if __name__ == "__main__":
    main()
