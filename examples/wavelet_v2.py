"""Example: Wavelet with clipped contour + slice plane (Vuetify 2).

Identical VTK pipeline to wavelet.py but uses Vuetify 2 widgets and layout.

Run:
    cd <repo_root>
    uv run python examples/wavelet_v2.py
"""

from trame.app import get_server
from trame.ui.vuetify2 import SinglePageLayout
from trame.widgets import html, vuetify2 as v2, vtk as vtk_widgets

from vtkmodules.vtkCommonDataModel import vtkPlane
from vtkmodules.vtkFiltersCore import vtkClipPolyData, vtkContourFilter, vtkCutter
from vtkmodules.vtkImagingCore import vtkRTAnalyticSource
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkPolyDataMapper,
    vtkRenderer,
    vtkRenderWindow,
    vtkRenderWindowInteractor,
)

# Required for VTK rendering in trame
import vtkmodules.vtkInteractionStyle  # noqa: F401
import vtkmodules.vtkRenderingOpenGL2  # noqa: F401

from trame_colormaps import Colorbar

# ---------------------------------------------------------------------------
# Trame setup
# ---------------------------------------------------------------------------
server = get_server(client_type="vue2")
state, ctrl = server.state, server.controller

# ---------------------------------------------------------------------------
# VTK pipeline
# ---------------------------------------------------------------------------

# Generate synthetic 3D data
wavelet = vtkRTAnalyticSource()
wavelet.SetWholeExtent(-10, 10, -10, 10, -10, 10)
wavelet.Update()

# Get the data range upfront
data_range = wavelet.GetOutput().GetPointData().GetScalars().GetRange()

# --- Clipping plane (removes front half so we can see inside) ---
clip_plane = vtkPlane()
clip_plane.SetOrigin(0, 0, 0)
clip_plane.SetNormal(0, 0, 1)

# --- Contour iso-surfaces, then clip them ---
contour = vtkContourFilter()
contour.SetInputConnection(wavelet.GetOutputPort())
contour.GenerateValues(6, 100.0, 250.0)
contour.Update()

clip_contour = vtkClipPolyData()
clip_contour.SetInputConnection(contour.GetOutputPort())
clip_contour.SetClipFunction(clip_plane)
clip_contour.Update()

contour_mapper = vtkPolyDataMapper()
contour_mapper.SetInputConnection(clip_contour.GetOutputPort())

contour_actor = vtkActor()
contour_actor.SetMapper(contour_mapper)

# --- Slice plane (perpendicular to clip — shows scalar gradient) ---
slice_plane = vtkPlane()
slice_plane.SetOrigin(0, 0, 0)
slice_plane.SetNormal(0, 1, 0)

slicer = vtkCutter()
slicer.SetInputConnection(wavelet.GetOutputPort())
slicer.SetCutFunction(slice_plane)
slicer.Update()

slice_mapper = vtkPolyDataMapper()
slice_mapper.SetInputConnection(slicer.GetOutputPort())

slice_actor = vtkActor()
slice_actor.SetMapper(slice_mapper)

# --- Renderer ---
renderer = vtkRenderer()
renderer.AddActor(contour_actor)
renderer.AddActor(slice_actor)
renderer.SetBackground(0.15, 0.15, 0.15)
renderer.ResetCamera()

render_window = vtkRenderWindow()
render_window.AddRenderer(renderer)
render_window.SetSize(1024, 768)

interactor = vtkRenderWindowInteractor()
interactor.SetRenderWindow(render_window)
interactor.GetInteractorStyle().SetCurrentStyleToTrackballCamera()

# ---------------------------------------------------------------------------
# Colormap controller
# ---------------------------------------------------------------------------

def get_data_array():
    """Return the active scalar array from the wavelet output."""
    ds = wavelet.GetOutput()
    if ds is None:
        return None
    return ds.GetPointData().GetScalars()


def do_render():
    # Sync the slice mapper whenever the controller swaps the CTF
    current_lut = contour_mapper.GetLookupTable()
    sr = contour_mapper.GetScalarRange()
    slice_mapper.SetLookupTable(current_lut)
    slice_mapper.SetScalarRange(sr)
    slice_mapper.Modified()
    if ctrl.view_update.exists():
        ctrl.view_update()


colorbar_up = Colorbar(
    server=server,
    variable_name="RTData",
    mapper=contour_mapper,
    data_array_fn=get_data_array,
    render_fn=do_render,
    orientation="horizontal",
    scalar_mode="default",
    popup_location="bottom",
)

colorbar_down = Colorbar(
    server=server,
    variable_name="RTData",
    mapper=contour_mapper,
    data_array_fn=get_data_array,
    render_fn=do_render,
    orientation="horizontal",
    scalar_mode="default",
    popup_location="top",
)

colorbar_left = Colorbar(
    server=server,
    variable_name="RTData",
    mapper=contour_mapper,
    data_array_fn=get_data_array,
    render_fn=do_render,
    orientation="vertical",
    scalar_mode="default",
    popup_location="end",
)

colorbar_right = Colorbar(
    server=server,
    variable_name="RTData",
    mapper=contour_mapper,
    data_array_fn=get_data_array,
    render_fn=do_render,
    orientation="vertical",
    scalar_mode="default",
    popup_location="start",
)

# ---------------------------------------------------------------------------
# UI state
# ---------------------------------------------------------------------------

state.show_up = False
state.show_down = True
state.show_left = False
state.show_right = False

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

with SinglePageLayout(server, full_height=True) as layout:
    layout.title.set_text("trame-colormaps: Wavelet (Vuetify 2)")

    with layout.toolbar:
        v2.VSpacer()
        with v2.VBtn(
            icon=True,
            click="show_up = !show_up",
            outlined=("!show_up",),
        ):
            v2.VIcon("mdi-arrow-up-bold")
        with v2.VBtn(
            icon=True,
            click="show_down = !show_down",
            outlined=("!show_down",),
        ):
            v2.VIcon("mdi-arrow-down-bold")
        with v2.VBtn(
            icon=True,
            click="show_left = !show_left",
            outlined=("!show_left",),
        ):
            v2.VIcon("mdi-arrow-left-bold")
        with v2.VBtn(
            icon=True,
            click="show_right = !show_right",
            outlined=("!show_right",),
        ):
            v2.VIcon("mdi-arrow-right-bold")
        with v2.VBtn(
            icon=True,
            click=ctrl.view_reset_camera,
        ):
            v2.VIcon("mdi-crop-free")

    with layout.content:
        with html.Div(style=(
            "display:grid;"
            "grid-template-rows:auto 1fr auto;"
            "grid-template-columns:auto 1fr auto;"
            "grid-template-areas:'up up up' 'left middle right' 'down down down';"
            "height:100%;overflow:hidden;"
        )):
            with html.Div(v_show="show_up", style="grid-area:up;"):
                colorbar_up.render()
            with html.Div(v_if="show_left", style="grid-area:left;width:3rem;position:relative;"):
                with html.Div(style="position:absolute;top:0;bottom:0;left:0;right:0;"):
                    colorbar_left.render()
            with html.Div(style="grid-area:middle;min-width:0;min-height:0;"):
                view = vtk_widgets.VtkRemoteView(
                    render_window,
                    ref="view",
                    style="width:100%;height:100%;",
                    interactive_ratio=1,
                )
                ctrl.view_update = view.update
                ctrl.view_reset_camera = view.reset_camera
            with html.Div(v_if="show_right", style="grid-area:right;width:3rem;position:relative;"):
                with html.Div(style="position:absolute;top:0;bottom:0;left:0;right:0;"):
                    colorbar_right.render()
            with html.Div(v_show="show_down", style="grid-area:down;"):
                colorbar_down.render()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    server.start()
