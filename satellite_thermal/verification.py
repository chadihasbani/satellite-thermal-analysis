"""Phase 1 checks against the analytical equilibrium and the time step.

These checks reuse the existing explicit Euler solver and the existing
physical parameters. They do not add eclipse, orbital geometry, or Earth
infrared radiation.
"""

from __future__ import annotations

from dataclasses import dataclass

from satellite_thermal.equilibrium import (
    analytical_equilibrium_temperature,
    radiative_time_constant_s,
)
from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.simulation import simulate_continuous_sunlight
from satellite_thermal.units import kelvin_to_celsius

# A 12-time-constant window leaves a linearized residual near 0.0002 K
# for a 30 K initial offset. The step is coarse because the equilibrium of
# explicit Euler is the same point as dT/dt = 0; the step does not move T_eq.
EQUILIBRIUM_TIME_CONSTANTS = 12.0
EQUILIBRIUM_TIME_STEP_S = 10.0

CONVERGENCE_DURATION_S = 5400.0
CONVERGENCE_TIME_STEPS_S = (10.0, 1.0, 0.5, 0.1)
REFERENCE_TIME_STEP_S = 0.1


@dataclass(frozen=True)
class EquilibriumApproach:
    """Comparison of a long sunlight run with the analytical steady temperature."""

    equilibrium_temperature_k: float
    final_temperature_k: float
    difference_k: float
    duration_s: float
    time_step_s: float
    time_constant_s: float


@dataclass(frozen=True)
class TimeStepResult:
    """One explicit-Euler step size over the fixed 5400 s window."""

    time_step_s: float
    final_temperature_k: float
    difference_from_reference_k: float


def approach_equilibrium(
    parameters: Phase1Parameters | None = None,
    time_constants: float = EQUILIBRIUM_TIME_CONSTANTS,
    time_step_s: float = EQUILIBRIUM_TIME_STEP_S,
) -> EquilibriumApproach:
    """Integrate constant sunlight long enough to approach T_eq.

    Duration is `time_constants` times the linearized radiative time constant
    evaluated at T_eq. The returned difference is T_final - T_eq, in kelvin.
    """
    settings = (parameters or Phase1Parameters()).validated()
    if time_constants <= 0.0:
        raise ValueError(f"time_constants must be greater than 0, got {time_constants}.")
    equilibrium_k = analytical_equilibrium_temperature(settings)
    time_constant_s = radiative_time_constant_s(equilibrium_k, settings)
    duration_s = time_constants * time_constant_s
    result = simulate_continuous_sunlight(
        duration_s=duration_s,
        time_step_s=time_step_s,
        parameters=settings,
    )
    final_k = result.temperature_k[-1]
    return EquilibriumApproach(
        equilibrium_temperature_k=equilibrium_k,
        final_temperature_k=final_k,
        difference_k=final_k - equilibrium_k,
        duration_s=duration_s,
        time_step_s=time_step_s,
        time_constant_s=time_constant_s,
    )


def time_step_convergence(
    duration_s: float = CONVERGENCE_DURATION_S,
    time_steps_s: tuple[float, ...] = CONVERGENCE_TIME_STEPS_S,
    reference_time_step_s: float = REFERENCE_TIME_STEP_S,
    parameters: Phase1Parameters | None = None,
) -> tuple[TimeStepResult, ...]:
    """Final temperatures for several Euler steps, each compared with the reference step.

    The difference is T(dt) - T(reference), in kelvin.
    """
    settings = (parameters or Phase1Parameters()).validated()
    if reference_time_step_s not in time_steps_s:
        raise ValueError("reference_time_step_s must be one of the requested steps.")

    finals = {
        step: simulate_continuous_sunlight(
            duration_s=duration_s,
            time_step_s=step,
            parameters=settings,
        ).temperature_k[-1]
        for step in time_steps_s
    }
    reference = finals[reference_time_step_s]
    return tuple(
        TimeStepResult(
            time_step_s=step,
            final_temperature_k=finals[step],
            difference_from_reference_k=finals[step] - reference,
        )
        for step in time_steps_s
    )


def verification_report(
    parameters: Phase1Parameters | None = None,
) -> str:
    """Text report of the analytical check, the long run, and the step study."""
    settings = (parameters or Phase1Parameters()).validated()
    equilibrium_k = analytical_equilibrium_temperature(settings)
    approach = approach_equilibrium(settings)
    steps = time_step_convergence(parameters=settings)

    lines = [
        "Phase 1 verification",
        "Simplified teaching model. Not a flight-temperature prediction.",
        "",
        "Analytical equilibrium",
        "T_eq = ((Q_solar + Q_internal) / (epsilon * sigma * A_radiating)) ** 0.25",
        f"T_eq = {equilibrium_k:.6f} K ({kelvin_to_celsius(equilibrium_k):.6f} °C)",
        "",
        "Long constant-sunlight integration",
        (
            f"Duration = {approach.duration_s:.3f} s "
            f"({approach.duration_s / approach.time_constant_s:.1f} linearized time constants)"
        ),
        f"Linearized time constant at T_eq = {approach.time_constant_s:.3f} s",
        f"Time step = {approach.time_step_s:g} s",
        f"Final temperature = {approach.final_temperature_k:.6f} K",
        f"T_final - T_eq = {approach.difference_k:.6e} K",
        "",
        f"Time-step study over {CONVERGENCE_DURATION_S:.0f} s",
        "Difference is T(dt) - T(0.1 s).",
        f"{'dt (s)':>10} {'T_final (K)':>16} {'difference (K)':>18}",
    ]
    for step in steps:
        lines.append(
            f"{step.time_step_s:10.1f} "
            f"{step.final_temperature_k:16.8f} "
            f"{step.difference_from_reference_k:18.6e}"
        )
    return "\n".join(lines)
