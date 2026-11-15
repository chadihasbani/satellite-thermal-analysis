"""Face-based solar absorption and multi-face radiative emission.

Solar absorption (per face)
---------------------------
    Q_solar,i = alpha_i * S * A_i * max(0, n_i · s)

where s is the unit vector from the spacecraft toward the Sun, n_i is the
outward inertial face normal, and S is the incident solar irradiance (0 in
eclipse). Summing over the six bus faces avoids double-counting because each
face has its own area and only the projected component max(0, n·s) contributes.

This projected-area form is the standard spacecraft surface heating relation
used in small-satellite thermal notes (absorbed solar ∝ α S A cosθ for
sunward faces; cosθ replaced by max(0, n·s) with unit vectors).

Radiative emission (isothermal node)
------------------------------------
    Q_radiated = sum_i (epsilon_i * sigma * A_i * T^4)

All six exterior faces radiate. There is no double-counting of area. If every
face shares the same epsilon, this equals epsilon * sigma * A_total * T^4.

Earth IR and albedo are intentionally not computed here; the enhanced model
retains the Version 1.0 effective-area planetary loads unless a later
checkpoint replaces them.
"""

from __future__ import annotations

from satellite_thermal.parameters import STEFAN_BOLTZMANN
from satellite_thermal.spacecraft_geometry import (
    FACE_NAMES,
    RectangularBusGeometry,
    face_normal_inertial,
)
from satellite_thermal.validation import (
    require_finite_number,
    require_non_negative,
    require_positive,
)


def _dot(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(name: str, vector: tuple[float, float, float]) -> tuple[float, float, float]:
    x = require_finite_number(f"{name}[0]", vector[0])
    y = require_finite_number(f"{name}[1]", vector[1])
    z = require_finite_number(f"{name}[2]", vector[2])
    magnitude = (x * x + y * y + z * z) ** 0.5
    if magnitude == 0.0:
        raise ValueError(f"{name} must be a non-zero vector.")
    return (x / magnitude, y / magnitude, z / magnitude)


def face_solar_cosine(
    normal_inertial: tuple[float, float, float],
    sun_direction_inertial: tuple[float, float, float],
) -> float:
    """max(0, n · s) for unit outward normal n and unit sunward vector s."""
    normal = _unit("normal_inertial", normal_inertial)
    sun = _unit("sun_direction_inertial", sun_direction_inertial)
    return max(0.0, _dot(normal, sun))


def projected_solar_area_m2(
    geometry: RectangularBusGeometry,
    body_x: tuple[float, float, float],
    body_y: tuple[float, float, float],
    body_z: tuple[float, float, float],
    sun_direction_inertial: tuple[float, float, float],
) -> float:
    """Sum of A_i max(0, n_i · s) over the six bus faces."""
    settings = geometry.validated()
    sun = _unit("sun_direction_inertial", sun_direction_inertial)
    total = 0.0
    for face_name in FACE_NAMES:
        normal = face_normal_inertial(settings, face_name, body_x, body_y, body_z)
        total += settings.face_area_m2(face_name) * face_solar_cosine(normal, sun)
    return total


def surface_solar_heating_w(
    geometry: RectangularBusGeometry,
    body_x: tuple[float, float, float],
    body_y: tuple[float, float, float],
    body_z: tuple[float, float, float],
    sun_direction_inertial: tuple[float, float, float],
    solar_flux_w_per_m2: float,
) -> float:
    """Total absorbed direct solar power over all bus faces, in watts.

    Returns 0 when solar_flux_w_per_m2 is 0 (eclipse / zero irradiance).
    """
    settings = geometry.validated()
    flux = require_non_negative("solar_flux_w_per_m2", solar_flux_w_per_m2)
    if flux == 0.0:
        return 0.0
    sun = _unit("sun_direction_inertial", sun_direction_inertial)
    total = 0.0
    for face_name in FACE_NAMES:
        normal = face_normal_inertial(settings, face_name, body_x, body_y, body_z)
        cosine = face_solar_cosine(normal, sun)
        if cosine == 0.0:
            continue
        optics = settings.optics_for_face(face_name)
        area = settings.face_area_m2(face_name)
        total += optics.absorptivity * flux * area * cosine
    return total


def surface_radiative_cooling_w(
    geometry: RectangularBusGeometry,
    temperature_k: float,
    stefan_boltzmann_w_per_m2_k4: float = STEFAN_BOLTZMANN,
) -> float:
    """Total IR emission from all six exterior faces to a 0 K sink, in watts."""
    settings = geometry.validated()
    temperature = require_positive("temperature_k", temperature_k)
    sigma = require_positive(
        "stefan_boltzmann_w_per_m2_k4", stefan_boltzmann_w_per_m2_k4
    )
    total = 0.0
    t4 = temperature**4
    for face_name in FACE_NAMES:
        optics = settings.optics_for_face(face_name)
        area = settings.face_area_m2(face_name)
        total += optics.emissivity * sigma * area * t4
    return total
