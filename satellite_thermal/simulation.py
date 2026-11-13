"""Explicit Euler integration for continuous sunlight.

The update is

    T_{n+1} = T_n + dt * (dT/dt evaluated at T_n)

with dT/dt from the single-node energy balance. The default step is 1 second.
A final shorter step is used when the duration is not an integer multiple of
the requested step, so the recorded end time matches the requested duration.

This integration is a teaching numerical method. It is not a certification
analysis and it does not predict actual satellite temperatures.
"""

from __future__ import annotations

from dataclasses import dataclass

from satellite_thermal.heat_transfer import temperature_derivative
from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.validation import require_non_negative, require_positive


@dataclass(frozen=True)
class SimulationResult:
    """Time history of one sunlight run.

    time_s:
        Sample times in seconds, beginning at 0.
    temperature_k:
        Node temperature in kelvin at each sample time.
    """

    time_s: tuple[float, ...]
    temperature_k: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.time_s) != len(self.temperature_k):
            raise ValueError("time_s and temperature_k must have the same length.")
        if len(self.time_s) == 0:
            raise ValueError("SimulationResult must contain at least one sample.")


def simulate_continuous_sunlight(
    duration_s: float,
    time_step_s: float = 1.0,
    parameters: Phase1Parameters | None = None,
) -> SimulationResult:
    """Integrate the node temperature over a period of uninterrupted sunlight.

    Parameters
    ----------
    duration_s:
        Simulated sunlit duration in seconds. Must be >= 0.
    time_step_s:
        Explicit Euler step in seconds. Must be > 0. Default is 1 second.
    parameters:
        Physical inputs. Defaults are the Phase 1 study values.

    Returns
    -------
    SimulationResult
        Time in seconds and temperature in kelvin, including the initial state.
    """
    duration = require_non_negative("duration_s", duration_s)
    time_step = require_positive("time_step_s", time_step_s)
    settings = (parameters or Phase1Parameters()).validated()

    time_s = [0.0]
    temperature_k = [settings.initial_temperature_k]
    elapsed_s = 0.0

    while elapsed_s < duration:
        step_s = min(time_step, duration - elapsed_s)
        rate_k_per_s = temperature_derivative(
            temperature_k=temperature_k[-1],
            mass_kg=settings.mass_kg,
            specific_heat_j_per_kg_k=settings.specific_heat_j_per_kg_k,
            absorptivity=settings.absorptivity,
            projected_area_m2=settings.projected_area_m2,
            solar_flux_w_per_m2=settings.solar_flux_w_per_m2,
            internal_heat_w=settings.internal_heat_w,
            emissivity=settings.emissivity,
            radiating_area_m2=settings.radiating_area_m2,
            stefan_boltzmann_w_per_m2_k4=settings.stefan_boltzmann_w_per_m2_k4,
        )
        elapsed_s += step_s
        temperature_k.append(temperature_k[-1] + step_s * rate_k_per_s)
        time_s.append(elapsed_s)

    return SimulationResult(time_s=tuple(time_s), temperature_k=tuple(temperature_k))
