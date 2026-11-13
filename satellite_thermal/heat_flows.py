"""Instantaneous heat-flow breakdown for a stored orbital simulation.

All values come from the same governing terms used by the integrator:

    Q_net = Q_solar + Q_earth_ir + Q_albedo + Q_internal - Q_radiated

This module does not invent illustrative numbers. Eclipse forces Q_solar and
Q_albedo to zero through the existing geometry helpers.
"""

from __future__ import annotations

from dataclasses import dataclass

from satellite_thermal.albedo import AlbedoParameters, albedo_heat_w_at_time
from satellite_thermal.earth_infrared import EarthInfraredParameters
from satellite_thermal.heat_transfer import radiative_cooling, solar_heating
from satellite_thermal.orbit import CircularOrbit
from satellite_thermal.orbital_simulation import OrbitalThermalResult, solar_flux_w_per_m2
from satellite_thermal.parameters import Phase1Parameters
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
) -> HeatFlowSnapshot:
    """Evaluate every energy-balance term at result sample `index`."""
    if index < 0 or index >= len(result.time_s):
        raise IndexError(f"index {index} is outside the simulation samples.")
    settings = thermal.validated()
    orbit_settings = orbit.validated()
    time_s = result.time_s[index]
    temperature_k = result.temperature_k[index]
    in_eclipse = result.in_eclipse[index]

    flux = solar_flux_w_per_m2(time_s, orbit_settings, settings)
    q_solar = solar_heating(
        settings.absorptivity, settings.projected_area_m2, flux
    )
    q_earth_ir = (
        result.earth_infrared_heat_w if include_earth_infrared else 0.0
    )
    if include_earth_infrared and earth_infrared is not None:
        # Prefer the constant used in the run; keep argument for API clarity.
        q_earth_ir = result.earth_infrared_heat_w
    q_albedo = (
        albedo_heat_w_at_time(time_s, orbit_settings, settings, albedo)
        if include_albedo
        else 0.0
    )
    q_internal = settings.internal_heat_w
    q_radiated = radiative_cooling(
        settings.emissivity,
        settings.radiating_area_m2,
        temperature_k,
        settings.stefan_boltzmann_w_per_m2_k4,
    )
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
