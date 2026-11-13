"""Time-step convergence for the Phase 3B orbital model (IR + albedo).

This checks numerical consistency of explicit Euler under the full teaching
environmental loads. It is not experimental validation.
"""

from __future__ import annotations

from dataclasses import dataclass

from satellite_thermal.orbital_simulation import simulate_orbital_eclipse
from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.units import kelvin_to_celsius

DEFAULT_STEPS_S = (10.0, 5.0, 1.0, 0.5)
REFERENCE_STEP_S = 0.5


@dataclass(frozen=True)
class ConvergenceRow:
    time_step_s: float
    minimum_k: float
    maximum_k: float
    final_k: float
    delta_minimum_k: float
    delta_maximum_k: float
    delta_final_k: float


def run_phase3b_timestep_convergence(
    orbit_count: int = 5,
    time_steps_s: tuple[float, ...] = DEFAULT_STEPS_S,
    reference_step_s: float = REFERENCE_STEP_S,
) -> tuple[ConvergenceRow, ...]:
    """Compare Phase 3B five-orbit metrics across several Euler steps."""
    if reference_step_s not in time_steps_s:
        raise ValueError("reference_step_s must be one of the requested steps.")
    finals = {}
    mins = {}
    maxs = {}
    for step in time_steps_s:
        result = simulate_orbital_eclipse(
            orbit_count=orbit_count,
            time_step_s=step,
            parameters=Phase1Parameters(),
            include_earth_infrared=True,
            include_albedo=True,
        )
        finals[step] = result.temperature_k[-1]
        mins[step] = min(result.temperature_k)
        maxs[step] = max(result.temperature_k)

    ref_final = finals[reference_step_s]
    ref_min = mins[reference_step_s]
    ref_max = maxs[reference_step_s]
    return tuple(
        ConvergenceRow(
            time_step_s=step,
            minimum_k=mins[step],
            maximum_k=maxs[step],
            final_k=finals[step],
            delta_minimum_k=mins[step] - ref_min,
            delta_maximum_k=maxs[step] - ref_max,
            delta_final_k=finals[step] - ref_final,
        )
        for step in time_steps_s
    )


def format_convergence_report(rows: tuple[ConvergenceRow, ...]) -> str:
    """Human-readable Phase 3B convergence table."""
    lines = [
        "Phase 3B time-step convergence (Earth IR + albedo, 5 orbits)",
        "Differences are relative to the finest listed step.",
        f"{'dt (s)':>8} {'Tmin C':>10} {'Tmax C':>10} {'Tfinal C':>11} "
        f"{'dTmin K':>10} {'dTfinal K':>11}",
    ]
    for row in rows:
        lines.append(
            f"{row.time_step_s:8.1f} "
            f"{kelvin_to_celsius(row.minimum_k):10.4f} "
            f"{kelvin_to_celsius(row.maximum_k):10.4f} "
            f"{kelvin_to_celsius(row.final_k):11.4f} "
            f"{row.delta_minimum_k:10.4e} "
            f"{row.delta_final_k:11.4e}"
        )
    return "\n".join(lines)
