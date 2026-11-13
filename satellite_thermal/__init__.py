"""Simplified single-node satellite thermal model.

Phase 1 is continuous sunlight. Phase 2 adds a circular orbit and a
cylindrical Earth shadow. The package is a learning model. It does not
predict the temperature of a real satellite.
"""

from satellite_thermal.equilibrium import (
    analytical_equilibrium_temperature,
    equilibrium_temperature_k,
    net_heat_w,
)
from satellite_thermal.heat_transfer import (
    radiative_cooling,
    solar_heating,
    temperature_derivative,
)
from satellite_thermal.orbit import CircularOrbit, in_eclipse_at_time, orbital_period_s
from satellite_thermal.orbital_simulation import simulate_orbital_eclipse, solar_flux_w_per_m2
from satellite_thermal.parameters import STEFAN_BOLTZMANN, Phase1Parameters
from satellite_thermal.simulation import SimulationResult, simulate_continuous_sunlight
from satellite_thermal.units import kelvin_to_celsius

__all__ = [
    "STEFAN_BOLTZMANN",
    "CircularOrbit",
    "Phase1Parameters",
    "SimulationResult",
    "analytical_equilibrium_temperature",
    "equilibrium_temperature_k",
    "in_eclipse_at_time",
    "kelvin_to_celsius",
    "net_heat_w",
    "orbital_period_s",
    "radiative_cooling",
    "simulate_continuous_sunlight",
    "simulate_orbital_eclipse",
    "solar_flux_w_per_m2",
    "solar_heating",
    "temperature_derivative",
]
