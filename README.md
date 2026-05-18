# trame-colormaps

Self-contained colormap module for managing VTK color transfer
functions, colorbar rendering, and interactive preset controls in Trame apps.

## Installation

```bash
pip install trame-colormaps
```

Or with uv:

```bash
uv add trame-colormaps
```

## Development

```bash
git clone https://github.com/Kitware/trame-colormaps.git
cd trame-colormaps
uv pip install -e ".[dev]"
pre-commit install
```

Run tests:

```bash
uv run pytest
```

Run the example app:

```bash
uv run python examples/wavelet.py
```

Lint and format:

```bash
uv run ruff check .
uv run ruff format .
```

### Releasing

1. Bump the version in `pyproject.toml`
2. Commit and tag: `git tag v<version>`
3. Push with tags: `git push --tags`
4. GitHub Actions will build and publish to PyPI automatically

## Screenshots

### Horizontal and vertical colorbars with preset picker

![Wavelet](docs/images/wavelet.png)

The wavelet example (`examples/wavelet.py`) shows four colorbars around a 3D view:
two horizontal bars (top and bottom) and two vertical bars (left and right).
Clicking any colorbar opens its control panel with preset picker, scale mode,
and discrete settings. Only one panel can be open at a time.

### Real-world integration — horizontal footer colorbar

![QuickView](docs/images/quickview.png)

A production app using `trame-colormaps` for climate data visualization.
Each data variable gets its own horizontal colorbar at the bottom of the view,
with symlog tick marks that adapt to the data range.

## Public API

Import via the trame namespace:

```python
from trame.dataclasses.colormaps import ColormapConfig
from trame.widgets.colormaps import HorizontalScalarBar, VerticalScalarBar, ColorMapEditor
```

| Symbol | Module | Purpose |
|--------|--------|---------|
| `ColormapConfig` | `trame_colormaps.dataclasses` | Reactive state model — owns CTF, mapper, presets, range, ticks |
| `HorizontalScalarBar` | `trame_colormaps.widgets` | Horizontal colorbar widget with built-in control panel |
| `VerticalScalarBar` | `trame_colormaps.widgets` | Vertical colorbar widget with built-in control panel |
| `ColorMapEditor` | `trame_colormaps.widgets` | Preset picker / control panel popup (used internally by scalar bars) |
| `buttons` | `trame_colormaps.widgets` | Returns button config dicts for the control panel toolbar |

## Preset Data Sources

All colormap presets are stored as JSON files under `src/trame_colormaps/presets/`.

### `paraview_colormaps.json` — Built-in Presets

- **Source:** [ParaView ColorMaps.json](https://gitlab.kitware.com/paraview/paraview/-/raw/master/Remoting/Views/ColorMaps.json)
- **License:** BSD-3-Clause
- **199 colormaps** including Brewer, matplotlib, and other community-contributed presets
- Presets that originally used `IndexedColors` (discrete/qualitative) have been
  converted to `RGBPoints` with evenly spaced control points for uniform handling

### `crameri_colormaps.json` — Crameri Scientific Colour Maps

- **Source:** [Fabio Crameri's Scientific Colour Maps](https://www.fabiocrameri.ch/colourmaps/)
- **License:** MIT
- **60 colormaps** — sequential, diverging, multi-sequential, cyclic, and categorical
- All are perceptually uniform and color-blind safe
- Downloaded from the [cmcrameri GitHub repository](https://github.com/callumrollo/cmcrameri)

### Colormap Usage Guide

| Category | Use When | Data Character |
|----------|----------|----------------|
| **Sequential** | Magnitude — more/less of something | Temperature, pressure, density |
| **Diverging** | Deviation — Δ from a reference value | Anomaly, residual, balance |
| **Cyclic** | Periodic — values that wrap around | Phase, angle, time-of-day |
| **Categorical** | Discrete labels — no inherent order | Material ID, region, class |

> **Note:** Categorical presets are excluded from `default_presets.json` because
> trame-colormaps generates its own discrete/categorical colormaps from any preset
> via the discrete banding feature.

#### Using Sequential Colormaps

Sequential colormaps encode **"more vs less"** — data that is ordered and one-sided
with no special reference value.

**Use when:**

- Data interpretation is monotonic: low → high
- There is no meaningful midpoint or zero crossing

**Examples:** temperature (no reference), density, probability, intensity, error magnitude (`|Δ|`).

**Properties:**

- Monotonic lightness — darker always means more (or less)
- No implied midpoint
- Easy to interpret quantitatively

**Good defaults:** Viridis, Plasma, batlow — perceptually uniform ramps.

#### Using Diverging Colormaps

Diverging colormaps encode **"above vs below reference"** — data with a meaningful
center value where you care about the direction of deviation.

**Use when:**

- There is a meaningful center (usually 0, but not always)
- You care about direction: below reference ← neutral → above reference

**Examples:** Δ = A − B, anomalies (value − mean), residuals, signed errors.

**Properties:**

- Two symmetric color branches around a neutral center (white/light gray)
- Encodes both sign and magnitude
- Must be centered correctly to avoid misinterpretation
- Should be perceptually balanced on both sides

**Common derived difference fields:**

1. **Absolute difference** — `Δ = A − B`
   Your primary case (simulation vs observation). Symmetric, interpretable.

2. **Relative / percent difference** — `Δ = (A − B) / B` or `Δ% = 100 × (A − B) / B`
   Useful when scale matters. Still centered at 0 → diverging applies.

3. **Deviation from a baseline** — `Δ = value − reference_value`
   Examples: temperature − freezing point, measurement − target threshold, field − spatial mean.

4. **Standardized anomaly** — `Δ = (value − mean) / std`
   Now Δ is in "number of standard deviations." Very common in climate and statistics.

5. **Log-ratio (for multiplicative differences)** — `Δ = log(A / B)`
   Symmetric around 0. Handles ratios cleanly and plays nicely with wide dynamic ranges.

**Diverging workflow:**

1. **Derive Δ field** — compute the difference quantity
2. **Choose scale** — linear or symlog (symlog for wide dynamic ranges near zero)
3. **Apply diverging colormap centered at 0** — toggle diverging mode
4. **Optional tolerance band (epsilon)** — suppress a dead zone around zero

#### Using Cyclic Colormaps

Cyclic colormaps encode **"wrap-around / periodic"** — data where start and end
represent the same value (0° ≡ 360°).

**Use when:**

- Data is periodic with no true endpoints
- There must be no visual discontinuity at the boundary

**Examples:** angle, phase, orientation, wind direction, time of day (circular).

**Properties:**

- Ends match seamlessly — color at min == color at max
- No discontinuity at boundaries
- Not suitable for ordered or magnitude data

#### Using Categorical Colormaps

Categorical colormaps encode **"different kinds, not ordered"** — discrete labels
with no inherent ranking.

**Use when:**

- Data represents discrete labels with no meaningful ordering
- You need maximum visual distinction between classes

**Examples:** material IDs, cluster labels, classes, region tags.

**Properties:**

- Distinct, maximally separated colors
- No gradient or implied ordering between colors
- Not suitable for continuous or magnitude data

> **Note:** In trame-colormaps, any preset can be turned into a categorical
> colormap via the discrete banding feature. This also serves as a way to apply
> color-based contours to continuous data — discrete bands act as visual
> iso-surfaces that segment the color range into distinct regions.

### `default_presets.json` — Active Preset List

A JSON array of colormap names that controls which presets are active by default.
Includes all non-Brewer presets, only the highest-count Brewer variants, and the
core 15 Crameri colormaps. Each preset entry includes a `"ColorBlindSafe"`
boolean field for filtering.

### Configuring Active Presets

On import, the active preset list is loaded from `default_presets.json`. Use
`set_active_presets()` to override it at runtime:

```python
from trame_colormaps.core.presets import get_active_presets, set_active_presets

# Get the current active list
presets = get_active_presets()

# Set from a Python list
set_active_presets(["Cool to Warm", "batlow", "vik", "Viridis (matplotlib)"])

# Set from a JSON file
set_active_presets("/path/to/my_presets.json")
```

## Usage

### Basic: single colorbar

```python
from trame.app import TrameApp
from trame.dataclasses.colormaps import ColormapConfig
from trame.widgets.colormaps import HorizontalScalarBar

class MyApp(TrameApp):
    def __init__(self, server=None):
        super().__init__(server)
        # ... set up VTK pipeline, mapper, etc. ...

        self.colormap = ColormapConfig(
            self.server,
            mapper=self.mapper,
            data_array_fn=self.get_data_array,
        ).set_data_array("Temperature", self.get_data_array, "point")

        # Re-render when the colormap updates the mapper
        self.colormap.watch(["mapper_change"], self.render)

        self._build_ui()

    def get_data_array(self):
        ds = self.source.GetOutput()
        return ds.GetPointData().GetScalars() if ds else None

    def render(self, *_):
        self.ctx.view.update()

    def _build_ui(self):
        with SinglePageLayout(self.server) as self.ui:
            with self.ui.content:
                # ... 3D view ...
                with self.colormap.provide_as("bar"):
                    HorizontalScalarBar("bar", popup_location="top")
```

### Multiple colorbars

Each `ColormapConfig` instance is independent. When one control panel opens,
all others close automatically:

```python
self.top = ColormapConfig(server, mapper=mapper, data_array_fn=get_data)
self.top.set_data_array("RTData", get_data, "point")

self.left = ColormapConfig(server, mapper=mapper, data_array_fn=get_data)
self.left.set_data_array("RTData", get_data, "point")

# In UI:
with self.top.provide_as("top"):
    HorizontalScalarBar("top", popup_location="bottom")

with self.left.provide_as("left"):
    VerticalScalarBar("left", popup_location="right")
```

### Updating color range after data changes

When the underlying data changes (e.g. new data loaded, pipeline update),
call `update_color_range()` to recompute the range, re-apply transforms,
and regenerate ticks:

```python
self.colormap.update_color_range()
```

### Switching data array at runtime

To color by a different variable without creating a new `ColormapConfig`:

```python
self.colormap.set_data_array(
    "Pressure",
    data_array_fn=lambda: get_pressure_array(),
    scalar_mode="point",  # "cell" (default), "point", or "default"
)
```

## ColormapConfig Fields

`ColormapConfig` in `dataclasses.py` is a `trame.app.dataclass.StateDataModel`
subclass. Fields fall into three groups:

| Field | Type | Default | Role |
|-------|------|---------|------|
| **User-settable (bound to UI, triggers reactive updates)** ||||
| `active_presets` | `list[str]` | `default_presets.json` | Preset names available in the picker |
| `preset` | `str` | `"BuGnYl"` | Active color preset name |
| `invert` | `bool` | `False` | Invert the transfer function |
| `color_blind` | `bool` | `False` | Filter preset list to color-blind safe |
| `use_log_scale` | `str` | `"linear"` | Scale mode: `"linear"`, `"log"`, `"symlog"` |
| `discrete_log` | `bool` | `False` | Enable discrete banding |
| `n_discrete_colors` | `int` | `4` | Color bands between ticks (linear) or per decade (log/symlog) |
| `n_ticks` | `int` | `5` | Number of tick marks on the colorbar |
| `color_value_min` | `str` | `"0"` | Manual range min (string for text field) |
| `color_value_max` | `str` | `"1"` | Manual range max (string for text field) |
| `override_range` | `bool` | `False` | Use manual range instead of data range |
| **Derived (computed internally, read by UI)** ||||
| `color_range` | `tuple[float, float]` | `(0, 1)` | Active min/max color range |
| `color_value_min_valid` | `bool` | `True` | Whether `color_value_min` parses as a valid float |
| `color_value_max_valid` | `bool` | `True` | Whether `color_value_max` parses as a valid float |
| `n_colors` | `int` | `255` | Number of LUT samples |
| `lut_img_h` | `str` | `""` | Base64 PNG data URI of the horizontal colorbar image |
| `lut_img_v` | `str` | `""` | Base64 PNG data URI of the vertical colorbar image |
| `color_ticks` | `list` | `[]` | Tick marks: `[{position, label, color}, ...]` |
| `effective_color_range` | `tuple[float, float]` | `(0, 1)` | Actual CTF range after transforms |
| `luts_normal` | `list` | `[]` | Sorted preset picker entries (normal) |
| `luts_inverted` | `list` | `[]` | Sorted preset picker entries (inverted) |
| **UI widget state** ||||
| `menu` | `bool` | `False` | Whether the control panel popup is open |
| `search` | `str \| None` | `None` | Preset search filter text |
| `orientation` | `str` | `"horizontal"` | Colorbar orientation |
| `mapper_change` | `int` | `0` | Server-only counter incremented on each mapper update |

### ColormapConfig Methods

| Method | Purpose |
|--------|---------|
| `set_data_array(name, fn, scalar_mode)` | Configure the mapper's scalar mode and color array, recompute range, re-apply preset |
| `update_color_range()` | Recompute range from data (or validate manual range), re-apply transforms, regenerate ticks |
| `update_color_preset(name, invert, log_scale, ...)` | Apply a preset with scale/discrete settings — also called automatically by reactive watchers |

### `ColormapConfig.__init__` parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `server` | *required* | Trame server instance (first positional arg) |
| `mapper` | `None` | VTK mapper — the CTF is set as its lookup table |
| `data_array_fn` | `None` | Callable returning the VTK data array for range computation |

## Configurable Parameters

### `core/presets.py` — function parameters

| Parameter | Default | Function | Description |
|-----------|---------|----------|-------------|
| `samples` | `255` | `generate_colormaps()` | Horizontal pixels in each colorbar image |
| `preset_list` | `default_presets.json` | `set_active_presets()` | List of names or path to JSON file |

### `core/ticks.py` — function parameters

| Parameter | Default | Function | Description |
|-----------|---------|----------|-------------|
| `n` | `5` | `get_nice_ticks()` | Desired number of ticks |
| `scale` | `"linear"` | `get_nice_ticks()` | Scale mode: `"linear"`, `"log"`, or `"symlog"` |
| `linthresh` | `1.0` | `get_nice_ticks()` | Linear threshold for log/symlog scales |

### Tick mark behavior

Tick marks are computed identically for discrete and continuous modes:

- **Linear**: evenly spaced (e.g. 20%, 40%, 60%, 80% for `n_ticks=4`)
- **Log**: only powers of 10 (decade marks) that fall within the data range
- **Symlog**: powers of 10 filtered by visual position spacing — ticks far from zero (where the symlog transform expands the scale) are shown at every decade, while ticks near zero (where the transform compresses values) are adaptively thinned to prevent overlap. Zero is always shown when it falls within the data range and away from edges.

The adaptive spacing uses the symlog-transformed position of each candidate tick: only ticks that are at least `100/n` percentage points apart in visual space are kept. This naturally produces a nonlinear stride — larger gaps near zero, smaller gaps at extremes.

### `core/transforms.py` — function parameters

| Parameter | Default | Function | Description |
|-----------|---------|----------|-------------|
| `n_sub` | `1` | All `apply_discrete_*()` functions | Number of color bands per gap (linear) or per decade (log/symlog) |
| `n_samples` | `256` | `apply_log()`, `apply_symlog()`, `apply_discrete_symlog()` | Resampling resolution for building continuous CTFs |

## Dependencies

| Package | Used in | Purpose |
|---------|---------|---------|
| **vtk** (`vtkmodules`) | `core/presets.py`, `core/transforms.py`, `dataclasses.py` | `vtkColorTransferFunction` for color sampling, `vtkPNGWriter`/`vtkImageData` for colorbar image generation, mapper wiring |
| **numpy** | `core/ticks.py`, `core/transforms.py`, `dataclasses.py` | Tick computation, LUT transforms, linthresh calculation |
| **trame** | `dataclasses.py`, `widgets.py` | `StateDataModel` for reactive config, Vuetify 3 widgets for UI |
| **trame-dataclass** | `dataclasses.py` | `StateDataModel` base class, `Sync`/`ServerOnly` field types, `provide_as` scoped slot |

## Module Structure

```
src/trame_colormaps/
├── __init__.py          # Package version
├── dataclasses.py       # ColormapConfig(StateDataModel) — reactive state, CTF, mapper wiring
├── widgets.py           # ColorMapEditor, HorizontalScalarBar, VerticalScalarBar
├── module.py            # No-op trame module stub for enable_module
├── core/
│   ├── __init__.py      # "Pure VTK/numpy, no trame dependency"
│   ├── presets.py       # Preset discovery, COLORBAR_CACHE, lut_to_img()
│   ├── ticks.py         # Tick computation (linear, log, symlog)
│   └── transforms.py   # LUT transforms (linear, log, symlog, discrete variants)
└── presets/
    ├── __init__.py      # Bundled preset JSON shipping
    ├── paraview_colormaps.json   # 199 ParaView built-in presets
    ├── crameri_colormaps.json    # 60 Crameri scientific colour maps
    └── default_presets.json      # Active preset list with color-blind-safe flags

src/trame/
├── dataclasses/
│   └── colormaps.py     # Re-exports ColormapConfig
└── widgets/
    └── colormaps.py     # Re-exports widgets, initialize(server)
```

## Layer Separation

| Layer | Modules | Dependencies |
|-------|---------|-------------|
| **Core** (pure VTK/numpy) | `core/presets.py`, `core/ticks.py`, `core/transforms.py` | VTK, numpy |
| **State + Logic** (Trame reactive model) | `dataclasses.py` | Core + trame |
| **Widgets** (UI) | `widgets.py` | trame (Vuetify 3, HTML) |

The core layer has zero Trame dependency and can be used independently
for headless colormap operations.

## Widget Structure

`HorizontalScalarBar` / `VerticalScalarBar` produce the following DOM tree:

```
html.Div  (top-level — flexbox row/column, bg-blue-grey-darken-2)
├── VMenu  (activator="parent" — click anywhere on the bar to open)
│   └── ColorMapEditor → VCard (360px popup)
│       ├── VCardItem: toggle buttons (color-blind, invert, scale, range, discrete)
│       ├── VCardItem: discrete color count input (v-show when discrete)
│       ├── VCardItem: min/max text fields (v-show when override_range)
│       ├── VDivider
│       └── VList: searchable preset list with thumbnail images
├── html.Div  (min range label)
├── html.Div  (colorbar image container, position:relative)
│   ├── html.Img  (LUT image — horizontal or vertical)
│   └── html.Div  (tick overlay, position:absolute, pointer-events:none)
│       └── html.Div v-for="tick in <name>.color_ticks"
│           ├── html.Div  (tick line)
│           └── html.Span (tick label)
└── html.Div  (max range label)
```

Template bindings use `<name>.*` via `config.provide_as("<name>")`.
When one control panel opens, all others close automatically.
The popup panel position is controlled by `popup_location`:
`"top"` → above bar, `"bottom"` → below, `"left"`/`"right"` for vertical bars.

## Examples

| File | Description |
|------|-------------|
| `examples/wavelet.py` | 4-region layout with horizontal + vertical colorbars around a 3D wavelet visualization |
