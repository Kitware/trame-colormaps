"""Example: Wavelet with clipped contour + slice plane.

A fully synthetic VTK pipeline that demonstrates trame-colormaps:
- vtkRTAnalyticSource generates a 3D structured grid with the "RTData" scalar.
- Contour iso-surfaces are clipped by a plane so you can see inside.
- A slice plane through the center shows continuous vs discrete coloring.
- ColormapController manages the color transfer function and wires it to
  the mapper.
- The colorbar widget provides an interactive preset picker, scale modes
  (linear / log / symlog), discrete banding, and manual range override.

Run:
    cd <repo_root>
    uv run python examples/wavelet.py
"""

# Required for VTK rendering in trame
import vtkmodules.vtkInteractionStyle  # noqa: F401
import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
from trame.app import TrameApp
from trame.ui.vuetify3 import SinglePageLayout
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

from trame.dataclasses import colormaps
from trame.widgets import html
from trame.widgets import vtk as vtk_widgets
from trame.widgets import vuetify3 as v3
from trame.widgets.colormaps import HorizontalScalarBar, VerticalScalarBar


class WaveletColorMapDemo(TrameApp):
    def __init__(self, server=None):
        super().__init__(server)
        self._setup_vtk()

        self.top = colormaps.ColormapConfig(
            self.server,
            mapper=self.contour_mapper,
            data_array_fn=self.get_data_array,
        ).set_data_array("RTData", self.get_data_array, "points")

        self.right = colormaps.ColormapConfig(
            self.server,
            mapper=self.contour_mapper,
            data_array_fn=self.get_data_array,
        ).set_data_array("RTData", self.get_data_array, "points")

        self.left = colormaps.ColormapConfig(
            self.server,
            mapper=self.slice_mapper,
            data_array_fn=self.get_data_array,
        ).set_data_array("RTData", self.get_data_array, "points")

        self.bottom = colormaps.ColormapConfig(
            self.server,
            mapper=self.slice_mapper,
            data_array_fn=self.get_data_array,
        ).set_data_array("RTData", self.get_data_array, "points")

        # Auto render when mapper update
        for colormap in [self.top, self.right, self.bottom, self.left]:
            colormap.watch(["mapper_change"], self.render)

        self._build_ui()

    def _setup_vtk(self):
        # Generate synthetic 3D data
        wavelet = vtkRTAnalyticSource()
        wavelet.SetWholeExtent(-10, 10, -10, 10, -10, 10)
        wavelet.Update()

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

        # Capture variables on class
        self.wavelet = wavelet
        self.render_window = render_window
        self.contour_mapper = contour_mapper
        self.slice_mapper = slice_mapper

    def get_data_array(self):
        """Return the active scalar array from the wavelet output."""
        self.wavelet.Update()
        ds = self.wavelet.GetOutput()
        return ds.GetPointData().GetScalars()

    def render(self, *_):
        self.ctx.view.update()

    def _build_ui(self):
        with SinglePageLayout(self.server, full_height=True) as self.ui:
            self.ui.title.set_text("trame-colormaps: Wavelet Example")

            with self.ui.content:
                with html.Div(
                    style=(
                        "display:grid;"
                        "grid-template-rows:auto 1fr auto;"
                        "grid-template-columns:auto 1fr auto;"
                        "grid-template-areas:"
                        "'up up up' 'left middle right' 'down down down';"
                        "height:100%;overflow:hidden;"
                    )
                ):
                    # Top
                    with (
                        html.Div(
                            v_show=("show_up", False),
                            style="grid-area:up;",
                        ),
                        self.top.provide_as("top"),
                    ):
                        HorizontalScalarBar("top", popup_location="bottom")

                    # Left
                    with (
                        html.Div(
                            v_if=("show_left", False),
                            style="grid-area:left;width:1rem;position:relative;",
                        ),
                        self.left.provide_as("left"),
                    ):
                        with html.Div(
                            style="position:absolute;top:0;bottom:0;left:0;right:0;"
                        ):
                            VerticalScalarBar("left", popup_location="right")

                    # Middle
                    with html.Div(
                        style="grid-area:middle;min-width:0;min-height:0;",
                    ):
                        vtk_widgets.VtkRemoteView(
                            self.render_window,
                            interactive_ratio=1,
                            ctx_name="view",
                        )

                    # Right
                    with (
                        html.Div(
                            v_if=("show_right", False),
                            style="grid-area:right;width:1rem;position:relative;",
                        ),
                        self.right.provide_as("right"),
                    ):
                        with html.Div(
                            style="position:absolute;top:0;bottom:0;left:0;right:0;"
                        ):
                            VerticalScalarBar("right", popup_location="left")

                    # Bottom
                    with (
                        html.Div(
                            v_show=("show_down", True),
                            style="grid-area:down;",
                        ),
                        self.bottom.provide_as("bottom"),
                    ):
                        HorizontalScalarBar("bottom", popup_location="top")

            with self.ui.toolbar:
                v3.VSpacer()
                v3.VBtn(
                    icon="mdi-arrow-up-bold",
                    click="show_up = !show_up",
                    density="compact",
                    variant=("show_up ? 'flat' : 'outlined'",),
                )
                v3.VBtn(
                    icon="mdi-arrow-down-bold",
                    click="show_down = !show_down",
                    density="compact",
                    variant=("show_down ? 'flat' : 'outlined'",),
                )
                v3.VBtn(
                    icon="mdi-arrow-left-bold",
                    click="show_left = !show_left",
                    density="compact",
                    variant=("show_left ? 'flat' : 'outlined'",),
                )
                v3.VBtn(
                    icon="mdi-arrow-right-bold",
                    click="show_right = !show_right",
                    density="compact",
                    variant=("show_right ? 'flat' : 'outlined'",),
                )
                v3.VBtn(
                    icon="mdi-crop-free",
                    click=self.ctx.view.reset_camera,
                    density="compact",
                )


def main():
    app = WaveletColorMapDemo()
    app.server.start()


if __name__ == "__main__":
    main()
