"""Instantaneous heat-flow breakdown for a stored orbital simulation.

All values come from the same governing terms used by the integrator:

    Q_net = Q_solar + Q_earth_ir + Q_albedo + Q_internal - Q_radiated

Legacy mode uses fixed projected / radiating areas. Enhanced mode uses the
face-based solar and multi-face radiation helpers. Eclipse forces Q_solar and
Q_albedo to zero through the existing geometry helpers.
"""

from __future__ import annotations

from dataclasses import dataclass

from satellite_thermal.albedo import AlbedoParameters, albedo_heat_w_at_time
from satellite_thermal.attitude import AttitudeMode, body_axes_inertial, parse_attitude_mode
from satellite_thermal.earth_infrared import EarthInfraredParameters
from satellite_thermal.heat_transfer import radiative_cooling, solar_heating
from satellite_thermal.orbit import (
    CircularOrbit,
    orbital_period_s,
    position_angle_rad,
    sun_direction,
)
from satellite_thermal.orbital_simulation import (
    THERMAL_MODEL_ENHANCED,
    THERMAL_MODEL_LEGACY,
    OrbitalThermalResult,
    parse_thermal_model,
    solar_flux_w_per_m2,
)
from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.spacecraft_geometry import RectangularBusGeometry
from satellite_thermal.surface_heating import (
    surface_radiative_cooling_w,
    surface_solar_heating_w,
)
from satellite_thermal.units import kelvin_to_celsius


@dataclass(frozen=True)
class HeatFlowSnapshot:
    """Heat rates at one simulation sample, in watts unless noted."""

    time_s: float
    temperature_k: float
    temperature_c: float
    in_eclipse: bool
    q_solar_w: float
    q_earth_ir_w: float
    q_albedo_w: float
    q_internal_w: float
    q_radiated_w: float
    q_net_w: float


def heat_flow_at_index(
    result: OrbitalThermalResult,
    index: int,
    thermal: Phase1Parameters,
    orbit: CircularOrbit,
    include_earth_infrared: bool,
    include_albedo: bool,
    earth_infrared: EarthInfraredParameters | None = None,
    albedo: AlbedoParameters | None = None,
    thermal_model: str = THERMAL_MODEL_LEGACY,
    geometry: RectangularBusGeometry | None = None,
    attitude_mode: str | AttitudeMode = AttitudeMode.FIXED_INERTIAL,
) -> HeatFlowSnapshot:
    """Evaluate every energy-balance term at result sample `index`."""
    if index < 0 or index >= len(result.time_s):
        raise IndexError(f"index {index} is outside the simulation samples.")
    settings = thermal.validated()
    orbit_settings = orbit.validated()
    model = parse_thermal_model(thermal_model)
    time_s = result.time_s[index]
    temperature_k = result.temperature_k[index]
    in_eclipse = result.in_eclipse[index]

    flux = solar_flux_w_per_m2(time_s, orbit_settings, settings)
    if model == THERMAL_MODEL_ENHANCED:
        bus = (geometry or RectangularBusGeometry()).validated()
        attitude = parse_attitude_mode(attitude_mode)
        sun = sun_direction(orbit_settings.beta_rad)
        angle = position_angle_rad(time_s, orbital_period_s(orbit_settings))
        body_x, body_y, body_z = body_axes_inertial(attitude, angle, sun)
        q_solar = surface_solar_heating_w(
            bus, body_x, body_y, body_z, sun, flux
        )
        q_radiated = surface_radiative_cooling_w(
            bus,
            temperature_k,
            settings.stefan_boltzmann_w_per_m2_k4,
        )
    else:
        q_solar = solar_heating(
            settings.absorptivity, settings.projected_area_m2, flux
        )
        q_radiated = radiative_cooling(
            settings.emissivity,
            settings.radiating_area_m2,
            temperature_k,
            settings.stefan_boltzmann_w_per_m2_k4,
        )

    q_earth_ir = (
        result.earth_infrared_heat_w if include_earth_infrared else 0.0
    )
    if include_earth_infrared and earth_infrared is not None:
        q_earth_ir = result.earth_infrared_heat_w
    q_albedo = (
        albedo_heat_w_at_time(time_s, orbit_settings, settings, albedo)
        if include_albedo
        else 0.0
    )
    q_internal = settings.internal_heat_w
    q_net = q_solar + q_earth_ir + q_albedo + q_internal - q_radiated
    return HeatFlowSnapshot(
        time_s=time_s,
        temperature_k=temperature_k,
        temperature_c=kelvin_to_celsius(temperature_k),
        in_eclipse=in_eclipse,
        q_solar_w=q_solar,
        q_earth_ir_w=q_earth_ir,
        q_albedo_w=q_albedo,
        q_internal_w=q_internal,
        q_radiated_w=q_radiated,
        q_net_w=q_net,
    )


def nearest_sample_index(result: OrbitalThermalResult, time_s: float) -> int:
    """Index of the stored sample closest to time_s."""
    if not result.time_s:
        raise ValueError("Result has no samples.")
    best = 0
    best_error = abs(result.time_s[0] - time_s)
    for index, sample in enumerate(result.time_s):
        error = abs(sample - time_s)
        if error < best_error:
            best = index
            best_error = error
    return best
