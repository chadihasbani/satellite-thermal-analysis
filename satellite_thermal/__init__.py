"""Simplified single-node satellite thermal model (Phase 1).

This package is a learning model. It does not predict the temperature of a
real satellite.
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
from satellite_thermal.parameters import STEFAN_BOLTZMANN, Phase1Parameters
from satellite_thermal.simulation import SimulationResult, simulate_continuous_sunlight
from satellite_thermal.units import kelvin_to_celsius

__all__ = [
    "STEFAN_BOLTZMANN",
    "Phase1Parameters",
    "SimulationResult",
    "analytical_equilibrium_temperature",
    "equilibrium_temperature_k",
    "kelvin_to_celsius",
    "net_heat_w",
    "radiative_cooling",
    "simulate_continuous_sunlight",
    "solar_heating",
    "temperature_derivative",
]
