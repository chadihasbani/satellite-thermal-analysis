"""Orbital thermal march: energy balance plus geometric eclipse.

Direct solar heating uses the Phase 1 flux while the satellite is in
sunlight and is set to zero while `in_eclipse_at_time` is true. Internal heat
and radiative emission keep the Phase 1 forms.

Phase 2 leaves Earth infrared off (default). Phase 3A may add a constant
absorbed Earth-infrared term that is available in both sunlight and eclipse.
Albedo is not included.

The integrator is the same explicit Euler update as Phase 1:

    T_new = T + dt * dT/dt(T, solar flux at the start of the step)

The run starts at the sunward position and covers an integer number of orbits.
"""

from __future__ import annotations

from dataclasses import dataclass

from satellite_thermal.earth_infrared import EarthInfraredParameters, earth_infrared_heat_w
from satellite_thermal.heat_transfer import temperature_derivative
from satellite_thermal.orbit import (
    CircularOrbit,
    eclipse_and_sunlight_durations_s,
    in_eclipse_at_time,
    orbital_period_s,
)
from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.validation import require_positive


def solar_flux_w_per_m2(
    time_s: float,
    orbit: CircularOrbit | None = None,
    parameters: Phase1Parameters | None = None,
) -> float:
    """Incident solar flux in W/m^2. Eclipse forces this value to zero."""
    settings = (parameters or Phase1Parameters()).validated()
    if in_eclipse_at_time(time_s, orbit):
        return 0.0
    return settings.solar_flux_w_per_m2


def eclipse_intervals_s(
    time_s: tuple[float, ...],
    in_eclipse: tuple[bool, ...],
) -> tuple[tuple[float, float], ...]:
    """Contiguous eclipse spans [start, end) described by each step's state.

    `in_eclipse[i]` is the shadow state used on the step that begins at
    `time_s[i]`. The final sample has no following step.
    """
    if len(time_s) != len(in_eclipse):
        raise ValueError("time_s and in_eclipse must have the same length.")
    if len(time_s) == 0:
        raise ValueError("time_s must contain at least one sample.")
    intervals: list[tuple[float, float]] = []
    start: float | None = None
    for index in range(len(time_s) - 1):
        if in_eclipse[index]:
            if start is None:
                start = time_s[index]
        elif start is not None:
            intervals.append((start, time_s[index]))
            start = None
    if start is not None:
        intervals.append((start, time_s[-1]))
    return tuple(intervals)


@dataclass(frozen=True)
class OrbitalThermalResult:
    """Temperature history of an integer number of circular orbits.

    in_eclipse[i] is the shadow state at time_s[i]. For every step except the
    final stored instant, that flag is the state used to choose the solar flux.
    earth_infrared_heat_w is the constant absorbed Earth IR used in the run,
    or 0.0 when Phase 2 (Earth IR off) is selected.
    """

    time_s: tuple[float, ...]
    temperature_k: tuple[float, ...]
    in_eclipse: tuple[bool, ...]
    period_s: float
    eclipse_duration_s: float
    sunlight_duration_s: float
    time_step_s: float
    orbit_count: int
    earth_infrared_heat_w: float = 0.0

    def __post_init__(self) -> None:
        if not (len(self.time_s) == len(self.temperature_k) == len(self.in_eclipse)):
            raise ValueError("time, temperature, and eclipse flags must have the same length.")
        if len(self.time_s) == 0:
            raise ValueError("OrbitalThermalResult must contain at least one sample.")


def simulate_orbital_eclipse(
    orbit_count: int = 5,
    time_step_s: float = 1.0,
    parameters: Phase1Parameters | None = None,
    orbit: CircularOrbit | None = None,
    include_earth_infrared: bool = False,
    earth_infrared: EarthInfraredParameters | None = None,
) -> OrbitalThermalResult:
    """Integrate the single-node balance over complete circular orbits.

    Solar heating is the Phase 1 value in sunlight and zero in eclipse.
    include_earth_infrared defaults to False so Phase 2 results are unchanged.
    When True, a constant Q_earth_ir is added in both sunlight and eclipse.
    """
    if isinstance(orbit_count, bool) or not isinstance(orbit_count, int) or orbit_count <= 0:
        raise ValueError(f"orbit_count must be a positive integer, got {orbit_count!r}.")
    if not isinstance(include_earth_infrared, bool):
        raise ValueError(
            f"include_earth_infrared must be a bool, got {include_earth_infrared!r}."
        )
    step_limit = require_positive("time_step_s", time_step_s)
    thermal = (parameters or Phase1Parameters()).validated()
    orbit_settings = (orbit or CircularOrbit()).validated()
    period = orbital_period_s(orbit_settings)
    eclipse_duration, sunlight_duration = eclipse_and_sunlight_durations_s(
        step_limit, orbit_settings
    )
    duration = orbit_count * period
    earth_ir_w = (
        earth_infrared_heat_w(orbit_settings, earth_infrared)
        if include_earth_infrared
        else 0.0
    )

    time_s = [0.0]
    temperature_k = [thermal.initial_temperature_k]
    eclipse_flags = [in_eclipse_at_time(0.0, orbit_settings)]
    elapsed = 0.0

    while elapsed < duration:
        step = min(step_limit, duration - elapsed)
        flux = solar_flux_w_per_m2(elapsed, orbit_settings, thermal)
        rate = temperature_derivative(
            temperature_k=temperature_k[-1],
            mass_kg=thermal.mass_kg,
            specific_heat_j_per_kg_k=thermal.specific_heat_j_per_kg_k,
            absorptivity=thermal.absorptivity,
            projected_area_m2=thermal.projected_area_m2,
            solar_flux_w_per_m2=flux,
            internal_heat_w=thermal.internal_heat_w,
            emissivity=thermal.emissivity,
            radiating_area_m2=thermal.radiating_area_m2,
            stefan_boltzmann_w_per_m2_k4=thermal.stefan_boltzmann_w_per_m2_k4,
            earth_infrared_heat_w=earth_ir_w,
        )
        elapsed += step
        temperature_k.append(temperature_k[-1] + step * rate)
        time_s.append(elapsed)
        eclipse_flags.append(in_eclipse_at_time(elapsed, orbit_settings))

    return OrbitalThermalResult(
        time_s=tuple(time_s),
        temperature_k=tuple(temperature_k),
        in_eclipse=tuple(eclipse_flags),
        period_s=period,
        eclipse_duration_s=eclipse_duration,
        sunlight_duration_s=sunlight_duration,
        time_step_s=step_limit,
        orbit_count=orbit_count,
        earth_infrared_heat_w=earth_ir_w,
    )
