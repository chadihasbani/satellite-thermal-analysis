"""Plotly 3D orbital scene driven by the existing orbit/eclipse geometry.

Visual geometry is illustrative. Satellite position and eclipse status come
from the same CircularOrbit helpers used by the thermal solver.
"""

from __future__ import annotations

import math

from satellite_thermal.orbit import (
    CircularOrbit,
    in_eclipse_at_time,
    orbital_period_s,
    orbital_radius_m,
    position_angle_rad,
    satellite_position_m,
    sun_direction,
)
from satellite_thermal.orbital_simulation import OrbitalThermalResult
from satellite_thermal.units import kelvin_to_celsius


def _sphere_mesh(radius_m: float, n_lat: int = 24, n_lon: int = 36):
    """Latitude/longitude mesh for a sphere centered at the origin."""
    xs: list[list[float]] = []
    ys: list[list[float]] = []
    zs: list[list[float]] = []
    for i in range(n_lat + 1):
        lat = math.pi * (-0.5 + i / n_lat)
        row_x: list[float] = []
        row_y: list[float] = []
        row_z: list[float] = []
        for j in range(n_lon + 1):
            lon = 2.0 * math.pi * j / n_lon
            row_x.append(radius_m * math.cos(lat) * math.cos(lon))
            row_y.append(radius_m * math.cos(lat) * math.sin(lon))
            row_z.append(radius_m * math.sin(lat))
        xs.append(row_x)
        ys.append(row_y)
        zs.append(row_z)
    return xs, ys, zs


def _shadow_cylinder_mesh(
    earth_radius_m: float,
    length_m: float,
    n_theta: int = 28,
    n_axial: int = 12,
):
    """Cylinder along -X (anti-sun for beta = 0) representing the umbra."""
    xs: list[list[float]] = []
    ys: list[list[float]] = []
    zs: list[list[float]] = []
    for i in range(n_axial + 1):
        x = -length_m * i / n_axial
        row_x: list[float] = []
        row_y: list[float] = []
        row_z: list[float] = []
        for j in range(n_theta + 1):
            ang = 2.0 * math.pi * j / n_theta
            row_x.append(x)
            row_y.append(earth_radius_m * math.cos(ang))
            row_z.append(earth_radius_m * math.sin(ang))
        xs.append(row_x)
        ys.append(row_y)
        zs.append(row_z)
    return xs, ys, zs


def _box_corners(
    center: tuple[float, float, float],
    axis_r: tuple[float, float, float],
    axis_t: tuple[float, float, float],
    axis_n: tuple[float, float, float],
    half_r: float,
    half_t: float,
    half_n: float,
) -> list[tuple[float, float, float]]:
    """Eight corners of a box in the local (radial, tangent, normal) frame."""
    corners: list[tuple[float, float, float]] = []
    for sr in (-1.0, 1.0):
        for st in (-1.0, 1.0):
            for sn in (-1.0, 1.0):
                corners.append(
                    (
                        center[0]
                        + sr * half_r * axis_r[0]
                        + st * half_t * axis_t[0]
                        + sn * half_n * axis_n[0],
                        center[1]
                        + sr * half_r * axis_r[1]
                        + st * half_t * axis_t[1]
                        + sn * half_n * axis_n[1],
                        center[2]
                        + sr * half_r * axis_r[2]
                        + st * half_t * axis_t[2]
                        + sn * half_n * axis_n[2],
                    )
                )
    return corners


def _mesh_from_boxes(
    boxes: list[list[tuple[float, float, float]]],
):
    """Combine one or more boxes into Mesh3d arrays."""
    # Corner order from _box_corners: indices 0..7 with loops sr, st, sn.
    faces = (
        (0, 1, 3),
        (0, 3, 2),
        (4, 6, 7),
        (4, 7, 5),
        (0, 4, 5),
        (0, 5, 1),
        (2, 3, 7),
        (2, 7, 6),
        (0, 2, 6),
        (0, 6, 4),
        (1, 5, 7),
        (1, 7, 3),
    )
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    i_idx: list[int] = []
    j_idx: list[int] = []
    k_idx: list[int] = []
    offset = 0
    for corners in boxes:
        for x, y, z in corners:
            xs.append(x)
            ys.append(y)
            zs.append(z)
        for a, b, c in faces:
            i_idx.append(offset + a)
            j_idx.append(offset + b)
            k_idx.append(offset + c)
        offset += 8
    return xs, ys, zs, i_idx, j_idx, k_idx


def _spacecraft_meshes(
    position: tuple[float, float, float],
    orbital_angle_rad: float,
    visual_scale_m: float,
):
    """Illustrative body + two solar panels. Orientation is fixed to the orbit frame.

    This is visual only. It does not simulate attitude dynamics.
    """
    # Local orbit-frame axes for an equatorial circular orbit.
    axis_r = (math.cos(orbital_angle_rad), math.sin(orbital_angle_rad), 0.0)
    axis_t = (-math.sin(orbital_angle_rad), math.cos(orbital_angle_rad), 0.0)
    axis_n = (0.0, 0.0, 1.0)

    body = _box_corners(
        position, axis_r, axis_t, axis_n,
        half_r=0.55 * visual_scale_m,
        half_t=0.45 * visual_scale_m,
        half_n=0.30 * visual_scale_m,
    )
    panel_offset = 1.15 * visual_scale_m
    panel_half_n = 1.35 * visual_scale_m
    panel_half_t = 0.18 * visual_scale_m
    panel_half_r = 0.08 * visual_scale_m
    panel_plus_center = (
        position[0] + panel_offset * axis_n[0],
        position[1] + panel_offset * axis_n[1],
        position[2] + panel_offset * axis_n[2],
    )
    panel_minus_center = (
        position[0] - panel_offset * axis_n[0],
        position[1] - panel_offset * axis_n[1],
        position[2] - panel_offset * axis_n[2],
    )
    panel_plus = _box_corners(
        panel_plus_center, axis_r, axis_t, axis_n,
        half_r=panel_half_r,
        half_t=panel_half_t,
        half_n=panel_half_n,
    )
    panel_minus = _box_corners(
        panel_minus_center, axis_r, axis_t, axis_n,
        half_r=panel_half_r,
        half_t=panel_half_t,
        half_n=panel_half_n,
    )
    body_mesh = _mesh_from_boxes([body])
    panel_mesh = _mesh_from_boxes([panel_plus, panel_minus])
    return body_mesh, panel_mesh


def build_orbit_3d_figure(
    result: OrbitalThermalResult,
    orbit: CircularOrbit,
    sample_index: int,
    title: str = "Orbital geometry",
):
    """Create a Plotly 3D figure for one synchronized simulation sample."""
    import plotly.graph_objects as go

    if sample_index < 0 or sample_index >= len(result.time_s):
        raise IndexError("sample_index out of range.")

    settings = orbit.validated()
    radius = orbital_radius_m(settings)
    period = orbital_period_s(settings)
    earth_r = settings.earth_radius_m
    sun = sun_direction(settings.beta_rad)

    # Orbit path (one revolution samples).
    path_x = []
    path_y = []
    path_z = []
    for k in range(181):
        angle = 2.0 * math.pi * k / 180.0
        pos = satellite_position_m(angle, radius)
        path_x.append(pos[0])
        path_y.append(pos[1])
        path_z.append(pos[2])

    time_s = result.time_s[sample_index]
    angle = position_angle_rad(time_s, period)
    sat = satellite_position_m(angle, radius)
    eclipsed = in_eclipse_at_time(time_s, settings)
    temp_c = kelvin_to_celsius(result.temperature_k[sample_index])
    status = "ECLIPSE" if eclipsed else "SUNLIT"

    earth_x, earth_y, earth_z = _sphere_mesh(earth_r)
    shadow_x, shadow_y, shadow_z = _shadow_cylinder_mesh(
        earth_r, length_m=2.2 * radius
    )

    # Dayside / nightside coloring using sun-facing hemisphere.
    earth_surfacecolor = []
    for row_x, row_y, row_z in zip(earth_x, earth_y, earth_z):
        color_row = []
        for x, y, z in zip(row_x, row_y, row_z):
            dot = (x * sun[0] + y * sun[1] + z * sun[2]) / earth_r
            color_row.append(max(dot, 0.0))
        earth_surfacecolor.append(color_row)

    sun_scale = 1.35 * radius
    figure = go.Figure()
    figure.add_trace(
        go.Surface(
            x=earth_x,
            y=earth_y,
            z=earth_z,
            surfacecolor=earth_surfacecolor,
            colorscale=[[0.0, "#0B1426"], [1.0, "#A8C5E8"]],
            showscale=False,
            opacity=1.0,
            name="Earth",
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Surface(
            x=shadow_x,
            y=shadow_y,
            z=shadow_z,
            surfacecolor=[[0.0 for _ in row] for row in shadow_x],
            colorscale=[[0.0, "#3A3A3C"], [1.0, "#3A3A3C"]],
            showscale=False,
            opacity=0.16,
            name="Eclipse shadow",
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter3d(
            x=path_x,
            y=path_y,
            z=path_z,
            mode="lines",
            line={"color": "#64D2FF", "width": 3},
            name="Orbit",
            hoverinfo="skip",
        )
    )
    # Visual scale is exaggerated so the craft is readable next to Earth.
    visual_scale = 0.060 * earth_r
    body_mesh, panel_mesh = _spacecraft_meshes(sat, angle, visual_scale)
    body_color = "#8E8E93" if eclipsed else "#F5F5F7"
    figure.add_trace(
        go.Mesh3d(
            x=body_mesh[0],
            y=body_mesh[1],
            z=body_mesh[2],
            i=body_mesh[3],
            j=body_mesh[4],
            k=body_mesh[5],
            color=body_color,
            opacity=1.0,
            name="Spacecraft",
            hovertemplate=(
                f"t = {time_s/60.0:.2f} min<br>"
                f"T = {temp_c:.2f} °C<br>"
                f"{status}<extra></extra>"
            ),
            flatshading=True,
            lighting={"ambient": 0.55, "diffuse": 0.7, "specular": 0.2},
        )
    )
    figure.add_trace(
        go.Mesh3d(
            x=panel_mesh[0],
            y=panel_mesh[1],
            z=panel_mesh[2],
            i=panel_mesh[3],
            j=panel_mesh[4],
            k=panel_mesh[5],
            color="#0A84FF",
            opacity=1.0,
            name="Solar panels",
            hoverinfo="skip",
            flatshading=True,
            lighting={"ambient": 0.5, "diffuse": 0.65, "specular": 0.15},
        )
    )
    figure.add_trace(
        go.Scatter3d(
            x=[0.0, sun_scale * sun[0]],
            y=[0.0, sun_scale * sun[1]],
            z=[0.0, sun_scale * sun[2]],
            mode="lines",
            line={"color": "#FFD60A", "width": 5},
            name="Sunlight",
            hoverinfo="skip",
        )
    )

    axis_style = {
        "showbackground": False,
        "showgrid": False,
        "zeroline": False,
        "showticklabels": False,
        "title": "",
        "showspikes": False,
    }
    figure.update_layout(
        title={
            "text": f"{title}  ·  {status}  ·  {temp_c:.1f} °C",
            "font": {"size": 13, "color": "#F5F5F7"},
            "x": 0.0,
            "xanchor": "left",
        },
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font={"color": "#F5F5F7", "family": "Helvetica, Arial, sans-serif"},
        scene={
            "xaxis": axis_style,
            "yaxis": axis_style,
            "zaxis": axis_style,
            "aspectmode": "data",
            "bgcolor": "#000000",
            # Closer camera so Earth + orbit fill the frame on load (no empty letterboxing).
            "camera": {
                "eye": {"x": 1.05, "y": 0.95, "z": 0.55},
                "center": {"x": 0.0, "y": 0.0, "z": 0.0},
            },
        },
        margin={"l": 0, "r": 0, "t": 36, "b": 0},
        legend={
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"size": 10, "color": "#AEAEB2"},
            "orientation": "h",
            "y": 0.01,
            "x": 0.0,
        },
        # Match the adjacent state panel height — do not create a tall scrollable well.
        height=520,
    )
    figure.add_annotation(
        text="Illustrative geometry · craft enlarged for visibility · not to scale",
        xref="paper",
        yref="paper",
        x=0.0,
        y=0.0,
        showarrow=False,
        align="left",
        font={"size": 10, "color": "#8E8E93"},
    )
    return figure
