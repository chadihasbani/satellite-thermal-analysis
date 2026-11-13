"""Analytical equilibrium of the Phase 1 energy balance.

Set dT/dt = 0 in

    m * cp * dT/dt = Q_solar + Q_internal - epsilon * sigma * A_radiating * T**4

The steady temperature in kelvin is

    T_eq = ((Q_solar + Q_internal) / (epsilon * sigma * A_radiating)) ** (1/4)

This is a property of the simplified emission model. It is not a predicted
on-orbit temperature.
"""

from __future__ import annotations

from satellite_thermal.heat_transfer import radiative_cooling, solar_heating
from satellite_thermal.parameters import STEFAN_BOLTZMANN, Phase1Parameters
from satellite_thermal.validation import require_finite_number, require_positive


def equilibrium_temperature_k(
    solar_heat_w: float,
    internal_heat_w: float,
    emissivity: float,
    radiating_area_m2: float,
    stefan_boltzmann_w_per_m2_k4: float = STEFAN_BOLTZMANN,
) -> float:
    """Steady temperature in kelvin for constant sunlight and constant heat.

    T_eq = ((Q_solar + Q_internal) / (epsilon * sigma * A_radiating)) ** (1/4)
    """
    solar = require_finite_number("solar_heat_w", solar_heat_w)
    internal = require_finite_number("internal_heat_w", internal_heat_w)
    epsilon = require_positive("emissivity", emissivity)
    if epsilon > 1.0:
        raise ValueError(f"emissivity must be between 0 and 1, got {epsilon}.")
    area = require_positive("radiating_area_m2", radiating_area_m2)
    sigma = require_positive(
        "stefan_boltzmann_w_per_m2_k4", stefan_boltzmann_w_per_m2_k4
    )
    heat_input_w = solar + internal
    if heat_input_w < 0.0:
        raise ValueError(
            "This emission-only balance has a real equilibrium only when "
            f"Q_solar + Q_internal is >= 0, got {heat_input_w}."
        )
    if heat_input_w == 0.0:
        return 0.0
    return (heat_input_w / (epsilon * sigma * area)) ** 0.25


def analytical_equilibrium_temperature(
    parameters: Phase1Parameters | None = None,
) -> float:
    """Phase 1 equilibrium temperature in kelvin, using the project heat rates."""
    settings = (parameters or Phase1Parameters()).validated()
    solar_w = solar_heating(
        settings.absorptivity,
        settings.projected_area_m2,
        settings.solar_flux_w_per_m2,
    )
    return equilibrium_temperature_k(
        solar_heat_w=solar_w,
        internal_heat_w=settings.internal_heat_w,
        emissivity=settings.emissivity,
        radiating_area_m2=settings.radiating_area_m2,
        stefan_boltzmann_w_per_m2_k4=settings.stefan_boltzmann_w_per_m2_k4,
    )


def net_heat_w(
    temperature_k: float,
    parameters: Phase1Parameters | None = None,
) -> float:
    """Q_solar + Q_internal - Q_radiated at one temperature, in watts."""
    settings = (parameters or Phase1Parameters()).validated()
    absorbed = solar_heating(
        settings.absorptivity,
        settings.projected_area_m2,
        settings.solar_flux_w_per_m2,
    )
    emitted = radiative_cooling(
        settings.emissivity,
        settings.radiating_area_m2,
        temperature_k,
        settings.stefan_boltzmann_w_per_m2_k4,
    )
    return absorbed + settings.internal_heat_w - emitted


def radiative_time_constant_s(
    temperature_k: float,
    parameters: Phase1Parameters | None = None,
) -> float:
    """Linearized cooling time constant m*cp / (4*epsilon*sigma*A*T**3), in seconds.

    Used only to choose a long verification duration. The transient solver
    still integrates the full T**4 balance.
    """
    settings = (parameters or Phase1Parameters()).validated()
    temperature = require_positive("temperature_k", temperature_k)
    conductance_w_per_k = (
        4.0
        * settings.emissivity
        * settings.stefan_boltzmann_w_per_m2_k4
        * settings.radiating_area_m2
        * temperature**3
    )
    capacity_j_per_k = settings.mass_kg * settings.specific_heat_j_per_kg_k
    return capacity_j_per_k / conductance_w_per_k
