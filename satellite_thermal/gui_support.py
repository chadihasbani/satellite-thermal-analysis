"""Helpers for the Streamlit GUI.

These functions only assemble existing model inputs and plots. They do not
re-implement the thermal equations.
"""

from __future__ import annotations

from dataclasses import dataclass

from satellite_thermal.albedo import AlbedoParameters
from satellite_thermal.earth_infrared import EarthInfraredParameters
from satellite_thermal.orbit import CircularOrbit
from satellite_thermal.orbital_simulation import (
    OrbitalThermalResult,
    eclipse_intervals_s,
    simulate_orbital_eclipse,
)
from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.units import kelvin_to_celsius
from satellite_thermal.validation import require_positive


@dataclass(frozen=True)
class GuiRunRequest:
    """User inputs collected by the GUI."""

    mass_kg: float
    specific_heat_j_per_kg_k: float
    initial_temperature_c: float
    absorptivity: float
    emissivity: float
    projected_area_m2: float
    radiating_area_m2: float
    earth_facing_area_m2: float
    albedo_area_m2: float
    internal_heat_w: float
    solar_flux_w_per_m2: float
    earth_olr_w_per_m2: float
    earth_bond_albedo: float
    altitude_km: float
    orbit_count: int
    time_step_s: float
    include_earth_infrared: bool
    include_albedo: bool


def default_gui_request() -> GuiRunRequest:
    """Defaults matching the Phase 3B teaching baseline."""
    return GuiRunRequest(
        mass_kg=5.0,
        specific_heat_j_per_kg_k=900.0,
        initial_temperature_c=20.0,
        absorptivity=0.60,
        emissivity=0.80,
        projected_area_m2=0.01,
        radiating_area_m2=0.06,
        earth_facing_area_m2=0.01,
        albedo_area_m2=0.01,
        internal_heat_w=5.0,
        solar_flux_w_per_m2=1361.0,
        earth_olr_w_per_m2=240.0,
        earth_bond_albedo=0.30,
        altitude_km=500.0,
        orbit_count=5,
        time_step_s=5.0,
        include_earth_infrared=True,
        include_albedo=True,
    )


def build_model_inputs(request: GuiRunRequest) -> tuple[
    Phase1Parameters,
    CircularOrbit,
    EarthInfraredParameters,
    AlbedoParameters,
]:
    """Convert GUI inputs into validated model dataclasses.

    Infrared absorptivity follows Kirchhoff's law: alpha_ir = epsilon.
    """
    thermal = Phase1Parameters(
        mass_kg=request.mass_kg,
        specific_heat_j_per_kg_k=request.specific_heat_j_per_kg_k,
        initial_temperature_k=request.initial_temperature_c + 273.15,
        solar_flux_w_per_m2=request.solar_flux_w_per_m2,
        absorptivity=request.absorptivity,
        emissivity=request.emissivity,
        projected_area_m2=request.projected_area_m2,
        radiating_area_m2=request.radiating_area_m2,
        internal_heat_w=request.internal_heat_w,
    ).validated()
    orbit = CircularOrbit(altitude_m=request.altitude_km * 1000.0).validated()
    earth_ir = EarthInfraredParameters(
        earth_olr_w_per_m2=request.earth_olr_w_per_m2,
        earth_facing_area_m2=request.earth_facing_area_m2,
        infrared_absorptivity=request.emissivity,
    ).validated()
    albedo = AlbedoParameters(
        earth_bond_albedo=request.earth_bond_albedo,
        albedo_area_m2=request.albedo_area_m2,
    ).validated()
    return thermal, orbit, earth_ir, albedo


def run_gui_simulation(request: GuiRunRequest) -> OrbitalThermalResult:
    """Run the existing orbital solver from a GUI request."""
    if isinstance(request.orbit_count, bool) or not isinstance(request.orbit_count, int):
        raise ValueError("orbit_count must be an integer.")
    if request.orbit_count <= 0:
        raise ValueError("orbit_count must be greater than 0.")
    require_positive("time_step_s", request.time_step_s)
    thermal, orbit, earth_ir, albedo = build_model_inputs(request)
    return simulate_orbital_eclipse(
        orbit_count=request.orbit_count,
        time_step_s=request.time_step_s,
        parameters=thermal,
        orbit=orbit,
        include_earth_infrared=request.include_earth_infrared,
        earth_infrared=earth_ir,
        include_albedo=request.include_albedo,
        albedo=albedo,
    )


def temperature_metrics_c(result: OrbitalThermalResult) -> dict[str, float]:
    """Initial, minimum, maximum, and final temperatures in Celsius."""
    return {
        "initial_c": kelvin_to_celsius(result.temperature_k[0]),
        "minimum_c": kelvin_to_celsius(min(result.temperature_k)),
        "maximum_c": kelvin_to_celsius(max(result.temperature_k)),
        "final_c": kelvin_to_celsius(result.temperature_k[-1]),
    }


def make_gui_temperature_figure(result: OrbitalThermalResult):
    """Build a Matplotlib figure for Streamlit display."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    time_min = [second / 60.0 for second in result.time_s]
    temp_c = [kelvin_to_celsius(temp_k) for temp_k in result.temperature_k]
    intervals = eclipse_intervals_s(result.time_s, result.in_eclipse)

    figure, axis = plt.subplots(figsize=(10, 4.8))
    for start_s, end_s in intervals:
        axis.axvspan(start_s / 60.0, end_s / 60.0, color="#f0c27a", alpha=0.45, zorder=0)
    axis.plot(time_min, temp_c, color="#0b6e4f", linewidth=1.8, zorder=2, label="Temperature")
    axis.set_xlabel("Time (minutes)")
    axis.set_ylabel("Temperature (°C)")
    axis.set_title("Single-node orbital temperature")
    axis.grid(True, alpha=0.35, zorder=1)
    axis.legend(
        handles=[
            axis.lines[0],
            Patch(facecolor="#f0c27a", edgecolor="none", alpha=0.9, label="Eclipse"),
        ],
        loc="best",
    )
    axis.text(
        0.0,
        -0.20,
        "Teaching model using the verified solvers. Not a flight prediction.",
        transform=axis.transAxes,
        fontsize=8,
        color="#444444",
    )
    figure.tight_layout()
    return figure
