"""Plotly 3D orbital scene driven by the existing orbit/eclipse geometry.

Visual geometry is illustrative. Satellite position and eclipse status come
from the same CircularOrbit helpers used by the thermal solver.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from satellite_thermal.attitude import AttitudeMode, body_axes_inertial, parse_attitude_mode
from satellite_thermal.orbit import (
    CircularOrbit,
    in_eclipse_at_time,
    orbital_period_s,
    orbital_radius_m,
    position_angle_rad,
    satellite_position_m,
    sun_direction,
)
from satellite_thermal.orbital_simulation import (
    THERMAL_MODEL_ENHANCED,
    OrbitalThermalResult,
    parse_thermal_model,
)
from satellite_thermal.units import kelvin_to_celsius

_EARTH_MAP_PATH = Path(__file__).resolve().parents[1] / "assets" / "earth_map.jpg"


@lru_cache(maxsize=2)
def _earth_texture_pixels(
    mtime_ns: int,
) -> tuple[int, int, tuple[tuple[int, int, int], ...]]:
    """Load the equirectangular Earth map once per file revision."""
    from PIL import Image

    del mtime_ns  # cache key only
    if not _EARTH_MAP_PATH.is_file():
        raise FileNotFoundError(f"Earth texture not found: {_EARTH_MAP_PATH}")
    image = Image.open(_EARTH_MAP_PATH).convert("RGB")
    width, height = image.size
    flat = getattr(image, "get_flattened_data", None)
    pixels = tuple(flat()) if callable(flat) else tuple(image.getdata())
    return width, height, pixels


def _sample_earth_rgb(lon_rad: float, lat_rad: float) -> tuple[int, int, int]:
    """Sample the Earth map at lon in [0, 2π) and lat in [-π/2, π/2]."""
    width, height, pixels = _earth_texture_pixels(_EARTH_MAP_PATH.stat().st_mtime_ns)
    u = (lon_rad / (2.0 * math.pi)) % 1.0
    v = 0.5 - (lat_rad / math.pi)
    v = min(max(v, 0.0), 1.0)
    col = min(int(u * width), width - 1)
    row = min(int(v * height), height - 1)
    return pixels[row * width + col]


def _orthonormal_basis(axis: tuple[float, float, float]):
    """Return two unit vectors perpendicular to axis."""
    ax, ay, az = axis
    if abs(ax) < 0.9:
        other = (1.0, 0.0, 0.0)
    else:
        other = (0.0, 1.0, 0.0)
    bx = ay * other[2] - az * other[1]
    by = az * other[0] - ax * other[2]
    bz = ax * other[1] - ay * other[0]
    bnorm = math.sqrt(bx * bx + by * by + bz * bz) or 1.0
    b = (bx / bnorm, by / bnorm, bz / bnorm)
    cx = ay * b[2] - az * b[1]
    cy = az * b[0] - ax * b[2]
    cz = ax * b[1] - ay * b[0]
    return b, (cx, cy, cz)


def _terminator_ring(
    earth_radius_m: float,
    sun: tuple[float, float, float],
    n_points: int = 96,
) -> tuple[list[float], list[float], list[float]]:
    """Day/night boundary circle on the Earth surface (plane normal to the Sun)."""
    b, c = _orthonormal_basis(sun)
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for k in range(n_points + 1):
        ang = 2.0 * math.pi * k / n_points
        ca = math.cos(ang)
        sa = math.sin(ang)
        xs.append(earth_radius_m * (ca * b[0] + sa * c[0]))
        ys.append(earth_radius_m * (ca * b[1] + sa * c[1]))
        zs.append(earth_radius_m * (ca * b[2] + sa * c[2]))
    return xs, ys, zs


def _sphere_triangle_indices(n_lat: int, n_lon: int):
    """Triangle indices for a lat/lon grid with (n_lat+1)*(n_lon+1) vertices."""
    i_idx: list[int] = []
    j_idx: list[int] = []
    k_idx: list[int] = []
    row = n_lon + 1
    for i in range(n_lat):
        for j in range(n_lon):
            a = i * row + j
            b = a + 1
            c = a + row
            d = c + 1
            i_idx.extend((a, a))
            j_idx.extend((b, d))
            k_idx.extend((d, c))
    return i_idx, j_idx, k_idx


@lru_cache(maxsize=4)
def _earth_textured_mesh(
    radius_m: float,
    sun_x: float,
    sun_y: float,
    sun_z: float,
    n_lat: int = 128,
    n_lon: int = 256,
    mtime_ns: int = 0,
):
    """Textured Earth sphere. Day/night comes from Plotly lighting + mild bake."""
    del mtime_ns  # cache key only
    sun = (sun_x, sun_y, sun_z)
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    colors: list[str] = []
    for i in range(n_lat + 1):
        lat = math.pi * (-0.5 + i / n_lat)
        cos_lat = math.cos(lat)
        sin_lat = math.sin(lat)
        for j in range(n_lon + 1):
            lon = 2.0 * math.pi * j / n_lon
            nx = cos_lat * math.cos(lon)
            ny = cos_lat * math.sin(lon)
            nz = sin_lat
            xs.append(radius_m * nx)
            ys.append(radius_m * ny)
            zs.append(radius_m * nz)
            # Mild bake so night side stays visible under lighting.
            illumination = nx * sun[0] + ny * sun[1] + nz * sun[2]
            shade = 0.22 + 0.78 * max(0.0, min(1.0, 0.55 + illumination / 0.45))
            r, g, b = _sample_earth_rgb(lon, lat)
            colors.append(
                f"rgb({int(r * shade)},{int(g * shade)},{int(b * shade)})"
            )

    i_idx, j_idx, k_idx = _sphere_triangle_indices(n_lat, n_lon)
    return xs, ys, zs, i_idx, j_idx, k_idx, colors


@lru_cache(maxsize=2)
def _atmosphere_mesh(radius_m: float, n_lat: int = 48, n_lon: int = 96):
    """Thin translucent shell for a soft atmospheric limb."""
    shell_r = radius_m * 1.018
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    colors: list[str] = []
    for i in range(n_lat + 1):
        lat = math.pi * (-0.5 + i / n_lat)
        cos_lat = math.cos(lat)
        sin_lat = math.sin(lat)
        for j in range(n_lon + 1):
            lon = 2.0 * math.pi * j / n_lon
            xs.append(shell_r * cos_lat * math.cos(lon))
            ys.append(shell_r * cos_lat * math.sin(lon))
            zs.append(shell_r * sin_lat)
            colors.append("rgb(120,170,255)")
    i_idx, j_idx, k_idx = _sphere_triangle_indices(n_lat, n_lon)
    return xs, ys, zs, i_idx, j_idx, k_idx, colors


def _orthonormal_basis_from_axis(
    axis: tuple[float, float, float],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Two unit vectors spanning the plane perpendicular to ``axis``."""
    ax, ay, az = axis
    # Prefer a reference that is not nearly parallel to the cylinder axis.
    if abs(ax) < 0.9:
        ref = (1.0, 0.0, 0.0)
    else:
        ref = (0.0, 1.0, 0.0)
    ux = ay * ref[2] - az * ref[1]
    uy = az * ref[0] - ax * ref[2]
    uz = ax * ref[1] - ay * ref[0]
    u_mag = math.sqrt(ux * ux + uy * uy + uz * uz)
    if u_mag == 0.0:
        raise ValueError("axis must be a non-zero vector.")
    u = (ux / u_mag, uy / u_mag, uz / u_mag)
    vx = ay * u[2] - az * u[1]
    vy = az * u[0] - ax * u[2]
    vz = ax * u[1] - ay * u[0]
    v_mag = math.sqrt(vx * vx + vy * vy + vz * vz)
    v = (vx / v_mag, vy / v_mag, vz / v_mag)
    return u, v


def _shadow_cylinder_mesh(
    earth_radius_m: float,
    length_m: float,
    sun_direction_vector: tuple[float, float, float] = (1.0, 0.0, 0.0),
    n_theta: int = 28,
    n_axial: int = 12,
):
    """Cylinder of radius Earth along -s (anti-sun), matching the umbra test."""
    sx, sy, sz = sun_direction_vector
    s_mag = math.sqrt(sx * sx + sy * sy + sz * sz)
    if s_mag == 0.0:
        raise ValueError("sun_direction_vector must be non-zero.")
    sun = (sx / s_mag, sy / s_mag, sz / s_mag)
    axis = (-sun[0], -sun[1], -sun[2])
    u, v = _orthonormal_basis_from_axis(axis)
    xs: list[list[float]] = []
    ys: list[list[float]] = []
    zs: list[list[float]] = []
    for i in range(n_axial + 1):
        along = length_m * i / n_axial
        row_x: list[float] = []
        row_y: list[float] = []
        row_z: list[float] = []
        for j in range(n_theta + 1):
            ang = 2.0 * math.pi * j / n_theta
            cos_a = math.cos(ang)
            sin_a = math.sin(ang)
            px = (
                axis[0] * along
                + earth_radius_m * (cos_a * u[0] + sin_a * v[0])
            )
            py = (
                axis[1] * along
                + earth_radius_m * (cos_a * u[1] + sin_a * v[1])
            )
            pz = (
                axis[2] * along
                + earth_radius_m * (cos_a * u[2] + sin_a * v[2])
            )
            row_x.append(px)
            row_y.append(py)
            row_z.append(pz)
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


def _offset(
    origin: tuple[float, float, float],
    axis: tuple[float, float, float],
    distance: float,
) -> tuple[float, float, float]:
    return (
        origin[0] + distance * axis[0],
        origin[1] + distance * axis[1],
        origin[2] + distance * axis[2],
    )


def _spacecraft_meshes(
    position: tuple[float, float, float],
    orbital_angle_rad: float,
    visual_scale_m: float,
    body_x: tuple[float, float, float] | None = None,
    body_y: tuple[float, float, float] | None = None,
    body_z: tuple[float, float, float] | None = None,
    body_length_m: float = 0.1,
    body_width_m: float = 0.1,
    body_height_m: float = 0.1,
):
    """Illustrative smallsat: bus, visual-only solar wings, antenna, thrusters.

    Bus orientation follows the prescribed body axes when provided (enhanced
    mode). Wing panels are decorative only and are not thermal surfaces.
    Absolute craft size is enlarged for visibility; bus box proportions follow
    length/width/height.
    """
    s = visual_scale_m
    if body_x is None or body_y is None or body_z is None:
        # Legacy visual default: LVLH-like (radial, along-track, orbit-normal).
        axis_x = (math.cos(orbital_angle_rad), math.sin(orbital_angle_rad), 0.0)
        axis_y = (-math.sin(orbital_angle_rad), math.cos(orbital_angle_rad), 0.0)
        axis_z = (0.0, 0.0, 1.0)
    else:
        axis_x, axis_y, axis_z = body_x, body_y, body_z

    # Map physical proportions onto the enlarged visual scale.
    max_dim = max(body_length_m, body_width_m, body_height_m, 1e-9)
    half_x = 0.55 * s * (body_length_m / max_dim)
    half_y = 0.55 * s * (body_width_m / max_dim)
    half_z = 0.55 * s * (body_height_m / max_dim)

    bus = _box_corners(
        position, axis_x, axis_y, axis_z,
        half_r=half_x, half_t=half_y, half_n=half_z,
    )
    deck = _box_corners(
        _offset(position, axis_x, 0.06 * s),
        axis_x, axis_y, axis_z,
        half_r=0.85 * half_x, half_t=0.85 * half_y, half_n=1.05 * half_z,
    )

    # Visual-only solar wings on ± body Y (not included in thermal face list).
    yoke_half_n = 0.18 * s
    panel_half_n = 0.12 * s
    panel_half_t = 1.35 * s
    panel_half_r = 0.05 * s
    yoke_offset = half_y + 0.20 * s
    panel_offset = half_y + 1.20 * s
    panels = []
    yokes = []
    for sign in (1.0, -1.0):
        yoke_center = _offset(position, axis_y, sign * yoke_offset)
        panel_center = _offset(position, axis_y, sign * panel_offset)
        yokes.append(
            _box_corners(
                yoke_center, axis_x, axis_y, axis_z,
                half_r=0.08 * s, half_t=yoke_half_n, half_n=0.08 * s,
            )
        )
        panels.append(
            _box_corners(
                panel_center, axis_x, axis_y, axis_z,
                half_r=panel_half_r, half_t=panel_half_t, half_n=panel_half_n,
            )
        )
        # Thin cell highlight strip on each wing (visual only).
        panels.append(
            _box_corners(
                _offset(panel_center, axis_x, 0.02 * s),
                axis_x, axis_y, axis_z,
                half_r=0.02 * s, half_t=panel_half_t * 0.92, half_n=panel_half_n * 0.92,
            )
        )

    # High-gain dish (stacked discs) on a short boom — visual detail only.
    boom_root = _offset(position, axis_y, -0.55 * s)
    boom = _box_corners(
        boom_root, axis_x, axis_y, axis_z,
        half_r=0.06 * s, half_t=0.28 * s, half_n=0.06 * s,
    )
    dish_center = _offset(position, axis_y, -0.95 * s)
    dish_outer = _box_corners(
        dish_center, axis_x, axis_y, axis_z,
        half_r=0.42 * s, half_t=0.05 * s, half_n=0.42 * s,
    )
    dish_inner = _box_corners(
        _offset(dish_center, axis_y, -0.04 * s),
        axis_x, axis_y, axis_z,
        half_r=0.28 * s, half_t=0.04 * s, half_n=0.28 * s,
    )

    # Aft thruster block + two nozzles — visual detail only.
    aft = _offset(position, axis_y, 0.58 * s)
    thruster_block = _box_corners(
        aft, axis_x, axis_y, axis_z,
        half_r=0.22 * s, half_t=0.12 * s, half_n=0.18 * s,
    )
    nozzles = []
    for side in (-0.12 * s, 0.12 * s):
        nozzles.append(
            _box_corners(
                _offset(_offset(aft, axis_z, side), axis_y, 0.16 * s),
                axis_x, axis_y, axis_z,
                half_r=0.07 * s, half_t=0.10 * s, half_n=0.07 * s,
            )
        )

    bus_mesh = _mesh_from_boxes([bus, deck, thruster_block])
    panel_mesh = _mesh_from_boxes(yokes + panels)
    detail_mesh = _mesh_from_boxes([boom, dish_outer, dish_inner, *nozzles])
    return bus_mesh, panel_mesh, detail_mesh


def build_orbit_3d_figure(
    result: OrbitalThermalResult,
    orbit: CircularOrbit,
    sample_index: int,
    title: str = "Orbital geometry",
    attitude_mode: str = AttitudeMode.FIXED_INERTIAL.value,
    body_length_m: float = 0.1,
    body_width_m: float = 0.1,
    body_height_m: float = 0.1,
    thermal_model: str = "legacy",
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
    model = parse_thermal_model(thermal_model)
    attitude = parse_attitude_mode(attitude_mode)

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

    shadow_x, shadow_y, shadow_z = _shadow_cylinder_mesh(
        earth_r, length_m=2.2 * radius, sun_direction_vector=sun
    )
    sun_arrow_scale = 1.55 * radius
    sun_line_x = [0.0, sun[0] * sun_arrow_scale]
    sun_line_y = [0.0, sun[1] * sun_arrow_scale]
    sun_line_z = [0.0, sun[2] * sun_arrow_scale]
    map_mtime = (
        _EARTH_MAP_PATH.stat().st_mtime_ns if _EARTH_MAP_PATH.is_file() else 0
    )
    earth_mesh = _earth_textured_mesh(
        earth_r, sun[0], sun[1], sun[2], mtime_ns=map_mtime
    )
    atmosphere = _atmosphere_mesh(earth_r)
    term_x, term_y, term_z = _terminator_ring(earth_r * 1.004, sun)
    # Plotly Mesh3d lightposition is capped at ±1e5.
    light_distance = 1.0e5
    sun_light = {
        "x": sun[0] * light_distance,
        "y": sun[1] * light_distance,
        "z": sun[2] * light_distance,
    }

    figure = go.Figure()
    figure.add_trace(
        go.Mesh3d(
            x=earth_mesh[0],
            y=earth_mesh[1],
            z=earth_mesh[2],
            i=earth_mesh[3],
            j=earth_mesh[4],
            k=earth_mesh[5],
            vertexcolor=earth_mesh[6],
            flatshading=False,
            lighting={
                "ambient": 0.35,
                "diffuse": 0.95,
                "fresnel": 0.15,
                "specular": 0.45,
                "roughness": 0.55,
            },
            lightposition=sun_light,
            name="Earth",
            hoverinfo="skip",
            showscale=False,
        )
    )
    figure.add_trace(
        go.Mesh3d(
            x=atmosphere[0],
            y=atmosphere[1],
            z=atmosphere[2],
            i=atmosphere[3],
            j=atmosphere[4],
            k=atmosphere[5],
            vertexcolor=atmosphere[6],
            opacity=0.12,
            flatshading=False,
            lighting={
                "ambient": 0.8,
                "diffuse": 0.4,
                "specular": 0.0,
                "roughness": 1.0,
            },
            lightposition=sun_light,
            name="Atmosphere",
            hoverinfo="skip",
            showscale=False,
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
            x=term_x,
            y=term_y,
            z=term_z,
            mode="lines",
            line={"color": "#FFE08A", "width": 3},
            name="Day / night terminator",
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
    figure.add_trace(
        go.Scatter3d(
            x=sun_line_x,
            y=sun_line_y,
            z=sun_line_z,
            mode="lines+markers",
            line={"color": "#FFD60A", "width": 5},
            marker={"size": [0, 5], "color": "#FFD60A"},
            name="Sun direction",
            hovertemplate=(
                f"β = {math.degrees(settings.beta_rad):.1f}°"
                "<extra>Sun direction</extra>"
            ),
        )
    )
    # Visual scale is exaggerated so the craft is readable next to Earth.
    visual_scale = 0.078 * earth_r
    if model == THERMAL_MODEL_ENHANCED:
        body_x, body_y, body_z = body_axes_inertial(attitude, angle, sun)
    else:
        body_x = body_y = body_z = None
    bus_mesh, panel_mesh, detail_mesh = _spacecraft_meshes(
        sat,
        angle,
        visual_scale,
        body_x=body_x,
        body_y=body_y,
        body_z=body_z,
        body_length_m=body_length_m,
        body_width_m=body_width_m,
        body_height_m=body_height_m,
    )
    bus_color = "#6E6E73" if eclipsed else "#E8E8ED"
    panel_color = "#1C3D6E" if eclipsed else "#0A4D8C"
    detail_color = "#8E8E93" if eclipsed else "#D4D4D8"
    craft_hover = (
        f"t = {time_s/60.0:.2f} min<br>"
        f"T = {temp_c:.2f} °C<br>"
        f"{status}<extra></extra>"
    )
    figure.add_trace(
        go.Mesh3d(
            x=bus_mesh[0],
            y=bus_mesh[1],
            z=bus_mesh[2],
            i=bus_mesh[3],
            j=bus_mesh[4],
            k=bus_mesh[5],
            color=bus_color,
            opacity=1.0,
            name="Spacecraft bus",
            hovertemplate=craft_hover,
            flatshading=True,
            lighting={"ambient": 0.45, "diffuse": 0.85, "specular": 0.35, "roughness": 0.4},
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
            color=panel_color,
            opacity=1.0,
            name="Solar arrays (visual only)",
            hoverinfo="skip",
            flatshading=True,
            lighting={"ambient": 0.35, "diffuse": 0.75, "specular": 0.55, "roughness": 0.25},
        )
    )
    figure.add_trace(
        go.Mesh3d(
            x=detail_mesh[0],
            y=detail_mesh[1],
            z=detail_mesh[2],
            i=detail_mesh[3],
            j=detail_mesh[4],
            k=detail_mesh[5],
            color=detail_color,
            opacity=1.0,
            name="Antenna / thrusters",
            hoverinfo="skip",
            flatshading=True,
            lighting={"ambient": 0.4, "diffuse": 0.8, "specular": 0.45, "roughness": 0.35},
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
    attitude_note = (
        f"enhanced · {attitude.value.replace('_', ' ')}"
        if model == THERMAL_MODEL_ENHANCED
        else "legacy visual orientation"
    )
    figure.add_annotation(
        text=(
            "Illustrative geometry · craft enlarged · not to scale · "
            f"wings visual-only · {attitude_note}"
        ),
        xref="paper",
        yref="paper",
        x=0.0,
        y=0.0,
        showarrow=False,
        align="left",
        font={"size": 10, "color": "#8E8E93"},
    )
    return figure
