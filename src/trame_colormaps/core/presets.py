"""Colormap preset discovery, caching, and image generation.

This module handles:
- Loading color presets from bundled JSON files (built-in + Crameri)
- Building VTK color transfer functions from JSON preset data
- Generating base64-encoded PNG colorbar images for each preset
- Converting a VTK color transfer function to a base64 PNG image
- Configurable active preset lists via JSON file or Python list
- CTF helper functions: apply_preset, invert, rescale, get/set points
"""

import base64
import json
from pathlib import Path

from vtkmodules.vtkCommonCore import vtkUnsignedCharArray
from vtkmodules.vtkCommonDataModel import vtkImageData
from vtkmodules.vtkIOImage import vtkPNGWriter
from vtkmodules.vtkRenderingCore import vtkColorTransferFunction

# --- Preset Loading ---

_PRESET_DIR = Path(__file__).parent.parent / "presets"


def _init_registry():
    """Load all presets and build the module-level registry constants.

    Returns:
        Tuple of (registry, all_names, color_blind_safe, default_presets).
    """

    def load(filename):
        path = _PRESET_DIR / filename
        if not path.exists():
            return []
        with open(path, "r") as f:
            return json.load(f)

    builtin = load("paraview_colormaps.json")
    crameri = load("crameri_colormaps.json")
    registry = {p["Name"]: p for p in builtin + crameri}
    all_names = set(registry.keys())
    color_blind = {
        n for n, p in registry.items() if p.get("ColorBlindSafe", False)
    }
    defaults_path = _PRESET_DIR / "default_presets.json"
    defaults = (
        json.loads(defaults_path.read_text())
        if defaults_path.exists()
        else sorted(all_names)
    )
    return registry, all_names, color_blind, defaults


PRESET_REGISTRY, ALL_PRESETS, COLOR_BLIND_SAFE, DEFAULT_PRESETS = _init_registry()

#: Module-level active preset list. Modified via set_active_presets().
_active_presets = [n for n in DEFAULT_PRESETS if n in PRESET_REGISTRY]


# --- CTF Builders ---


def _build_ctf(preset):
    """Build a vtkColorTransferFunction from a preset dict.

    Args:
        preset: dict with "RGBPoints" (flat list: [x, r, g, b, ...])
                and "ColorSpace" (e.g., "RGB", "HSV", "Lab", "Diverging").

    Returns:
        vtkColorTransferFunction configured with the preset's control points.
    """
    ctf = vtkColorTransferFunction()
    color_space = preset.get("ColorSpace", "RGB")
    if color_space == "Diverging":
        ctf.SetColorSpaceToDiverging()
    elif color_space == "HSV":
        ctf.SetColorSpaceToHSV()
    elif color_space == "Lab":
        ctf.SetColorSpaceToLab()
    else:
        ctf.SetColorSpaceToRGB()

    points = preset["RGBPoints"]
    for i in range(0, len(points), 4):
        ctf.AddRGBPoint(points[i], points[i + 1], points[i + 2], points[i + 3])

    return ctf


def get_active_presets():
    """Return the current active preset name list.

    Returns:
        List of preset names that exist in PRESET_REGISTRY.
    """
    return list(_active_presets)


def set_active_presets(preset_list):
    """Set the active preset list.

    Args:
        preset_list: A list of preset names, or a path (str or Path) to a
            JSON file containing a list of names. Names not found in
            PRESET_REGISTRY are silently ignored.
    """
    global _active_presets

    if isinstance(preset_list, (str, Path)):
        path = Path(preset_list)
        names = json.loads(path.read_text())
    else:
        names = list(preset_list)

    _active_presets = [n for n in names if n in PRESET_REGISTRY]


# --- Image Generation ---


def _ctf_to_base64_png_h(ctf, samples=255):
    """Render a vtkColorTransferFunction to a horizontal base64 PNG data URI.

    Args:
        ctf: A vtkColorTransferFunction with at least one control point.
        samples: Number of horizontal pixels in the colorbar image.

    Returns:
        Base64-encoded PNG image as a data URI string.
    """
    rgb = [0.0, 0.0, 0.0]
    colorArray = vtkUnsignedCharArray()
    colorArray.SetNumberOfComponents(3)
    colorArray.SetNumberOfTuples(samples)
    imgData = vtkImageData()
    imgData.SetDimensions(samples, 1, 1)
    imgData.GetPointData().SetScalars(colorArray)
    writer = vtkPNGWriter()
    writer.WriteToMemoryOn()
    writer.SetInputData(imgData)
    writer.SetCompressionLevel(1)

    v_min, v_max = ctf.GetRange()
    step = (v_max - v_min) / (samples - 1) if samples > 1 else 0

    for i in range(samples):
        value = v_min + step * float(i)
        ctf.GetColor(value, rgb)
        r = int(round(rgb[0] * 255))
        g = int(round(rgb[1] * 255))
        b = int(round(rgb[2] * 255))
        colorArray.SetTuple3(i, r, g, b)

    writer.Write()
    base64_img = base64.standard_b64encode(writer.GetResult()).decode("utf-8")
    return f"data:image/png;base64,{base64_img}"


def _ctf_to_base64_png_v(ctf, samples=255):
    """Render a vtkColorTransferFunction to a vertical base64 PNG data URI.

    The image is 1px wide and *samples* px tall.  Row 0 is the bottom
    of the image in VTK, filled min→max (bottom-to-top).

    Args:
        ctf: A vtkColorTransferFunction with at least one control point.
        samples: Number of vertical pixels in the colorbar image.

    Returns:
        Base64-encoded PNG image as a data URI string.
    """
    rgb = [0.0, 0.0, 0.0]
    colorArray = vtkUnsignedCharArray()
    colorArray.SetNumberOfComponents(3)
    colorArray.SetNumberOfTuples(samples)
    imgData = vtkImageData()
    imgData.SetDimensions(1, samples, 1)
    imgData.GetPointData().SetScalars(colorArray)
    writer = vtkPNGWriter()
    writer.WriteToMemoryOn()
    writer.SetInputData(imgData)
    writer.SetCompressionLevel(1)

    v_min, v_max = ctf.GetRange()
    step = (v_max - v_min) / (samples - 1) if samples > 1 else 0

    # Row 0 = bottom of image in VTK, so fill bottom-to-top (min→max).
    for i in range(samples):
        value = v_min + step * float(i)
        ctf.GetColor(value, rgb)
        r = int(round(rgb[0] * 255))
        g = int(round(rgb[1] * 255))
        b = int(round(rgb[2] * 255))
        colorArray.SetTuple3(i, r, g, b)

    writer.Write()
    base64_img = base64.standard_b64encode(writer.GetResult()).decode("utf-8")
    return f"data:image/png;base64,{base64_img}"


def lut_to_img_h(ctf):
    """Convert a vtkColorTransferFunction to a horizontal base64 PNG data URI.

    Args:
        ctf: A vtkColorTransferFunction.

    Returns:
        Base64-encoded PNG data URI string (wide, 1px tall).
    """
    return _ctf_to_base64_png_h(ctf)


def lut_to_img_v(ctf):
    """Convert a vtkColorTransferFunction to a vertical base64 PNG data URI.

    Args:
        ctf: A vtkColorTransferFunction.

    Returns:
        Base64-encoded PNG data URI string (1px wide, tall).
    """
    return _ctf_to_base64_png_v(ctf)


def generate_colormaps(samples=255):
    """Generate base64 PNG colorbar images (normal + inverted) for every preset.

    Args:
        samples: Number of horizontal pixels in each colorbar image.

    Returns:
        dict mapping preset name to {"normal": data_uri, "inverted": data_uri}.
    """
    color_maps = {}

    for name, preset in PRESET_REGISTRY.items():
        ctf = _build_ctf(preset)
        normal_img = _ctf_to_base64_png_h(ctf, samples=samples)

        # Build inverted CTF
        points = preset["RGBPoints"]
        n_points = len(points) // 4
        x_values = [points[i * 4] for i in range(n_points)]
        x_min, x_max = x_values[0], x_values[-1]

        ctf_inv = vtkColorTransferFunction()
        color_space = preset.get("ColorSpace", "RGB")
        if color_space == "Diverging":
            ctf_inv.SetColorSpaceToDiverging()
        elif color_space == "HSV":
            ctf_inv.SetColorSpaceToHSV()
        elif color_space == "Lab":
            ctf_inv.SetColorSpaceToLab()
        else:
            ctf_inv.SetColorSpaceToRGB()

        for i in range(n_points):
            x = x_min + (x_max - (points[i * 4])) 
            r, g, b = points[i * 4 + 1], points[i * 4 + 2], points[i * 4 + 3]
            ctf_inv.AddRGBPoint(x, r, g, b)

        inverted_img = _ctf_to_base64_png_h(ctf_inv, samples=samples)
        color_maps[name] = {"normal": normal_img, "inverted": inverted_img}

    return color_maps


#: Module-level cache of base64 colorbar images, keyed by preset name.
#: Built once at import time. Access via get_cached_colorbar_image().
COLORBAR_CACHE = generate_colormaps()


def get_cached_colorbar_image(colormap_name, inverted=False):
    """Get a cached colorbar image for a given colormap.

    Args:
        colormap_name: Preset name (e.g., "Cool to Warm", "batlow").
        inverted: Whether to get the inverted version.

    Returns:
        Base64-encoded PNG image as a data URI, or empty string if not found.
    """
    if colormap_name in COLORBAR_CACHE:
        variant = "inverted" if inverted else "normal"
        return COLORBAR_CACHE[colormap_name].get(variant, "")

    return ""


def get_preset_ctf(name):
    """Build and return a vtkColorTransferFunction for a named preset.

    Args:
        name: Preset name (must exist in PRESET_REGISTRY).

    Returns:
        vtkColorTransferFunction or None if name not found.
    """
    preset = PRESET_REGISTRY.get(name)
    if preset is None:
        return None
    return _build_ctf(preset)


# --- CTF Helper Functions ---


def get_rgb_points(ctf):
    """Read control points from a vtkColorTransferFunction as a flat list.

    Returns:
        Flat list [x, r, g, b, x, r, g, b, ...].
    """
    n = ctf.GetSize()
    pts = []
    val = [0.0] * 6  # x, r, g, b, midpoint, sharpness
    for i in range(n):
        ctf.GetNodeValue(i, val)
        pts.extend([val[0], val[1], val[2], val[3]])
    return pts


def set_rgb_points(ctf, points):
    """Replace all control points on a vtkColorTransferFunction.

    Args:
        ctf: vtkColorTransferFunction.
        points: Flat list [x, r, g, b, ...].
    """
    ctf.RemoveAllPoints()
    for i in range(0, len(points), 4):
        ctf.AddRGBPoint(points[i], points[i + 1], points[i + 2], points[i + 3])


def apply_preset(ctf, name):
    """Load a named preset from PRESET_REGISTRY into a CTF.

    Args:
        ctf: vtkColorTransferFunction.
        name: Preset name (must exist in PRESET_REGISTRY).
    """
    preset = PRESET_REGISTRY.get(name)
    if preset is None:
        return
    ctf.RemoveAllPoints()
    _apply_color_space(ctf, preset.get("ColorSpace", "RGB"))
    points = preset["RGBPoints"]
    for i in range(0, len(points), 4):
        ctf.AddRGBPoint(points[i], points[i + 1], points[i + 2], points[i + 3])


def invert_ctf(ctf):
    """Invert the control points of a vtkColorTransferFunction in place.

    Args:
        ctf: vtkColorTransferFunction.
    """
    pts = get_rgb_points(ctf)
    n = len(pts) // 4
    if n < 2:
        return
    x_min, x_max = pts[0], pts[-4]
    new_pts = []
    for i in range(n):
        x = x_min + (x_max - pts[i * 4])
        new_pts.extend([x, pts[i * 4 + 1], pts[i * 4 + 2], pts[i * 4 + 3]])
    set_rgb_points(ctf, new_pts)


def rescale_ctf(ctf, new_min, new_max):
    """Rescale control points to a new [new_min, new_max] range.

    Args:
        ctf: vtkColorTransferFunction.
        new_min: New minimum scalar value.
        new_max: New maximum scalar value.
    """
    pts = get_rgb_points(ctf)
    n = len(pts) // 4
    if n < 2:
        return
    old_min, old_max = pts[0], pts[-4]
    old_range = old_max - old_min
    if old_range == 0:
        return
    new_range = new_max - new_min
    new_pts = []
    for i in range(n):
        t = (pts[i * 4] - old_min) / old_range
        x = new_min + t * new_range
        new_pts.extend([x, pts[i * 4 + 1], pts[i * 4 + 2], pts[i * 4 + 3]])
    set_rgb_points(ctf, new_pts)


def map_to_log_space(ctf):
    """Remap control points from linear to log10 spacing.

    Args:
        ctf: vtkColorTransferFunction with positive-only range.
    """
    import math

    pts = get_rgb_points(ctf)
    n = len(pts) // 4
    if n < 2:
        return
    x_min, x_max = pts[0], pts[-4]
    if x_min <= 0 or x_max <= 0:
        return
    log_min = math.log10(x_min)
    log_max = math.log10(x_max)
    old_range = x_max - x_min
    if old_range == 0:
        return
    new_pts = []
    for i in range(n):
        t = (pts[i * 4] - x_min) / old_range
        log_x = log_min + t * (log_max - log_min)
        new_pts.extend([10.0 ** log_x, pts[i * 4 + 1], pts[i * 4 + 2], pts[i * 4 + 3]])
    set_rgb_points(ctf, new_pts)


def _apply_color_space(ctf, color_space):
    """Set the color space on a vtkColorTransferFunction."""
    if color_space == "Diverging":
        ctf.SetColorSpaceToDiverging()
    elif color_space == "HSV":
        ctf.SetColorSpaceToHSV()
    elif color_space == "Lab":
        ctf.SetColorSpaceToLab()
    else:
        ctf.SetColorSpaceToRGB()


def get_preset_metadata(name):
    """Return metadata dict for a named preset (without RGBPoints).

    Args:
        name: Preset name.

    Returns:
        dict with keys like ColorSpace, Creator, Source, License, Category, etc.
        Returns None if name not found.
    """
    preset = PRESET_REGISTRY.get(name)
    if preset is None:
        return None
    return {k: v for k, v in preset.items() if k != "RGBPoints"}
