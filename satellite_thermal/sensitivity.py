"""Phase 4 one-at-a-time parameter sensitivity studies.

Baseline
--------
The Phase 3B configuration: circular 500 km orbit, geometric eclipse, Earth
infrared on, albedo on, and the original thermal parameters.

Method
------
Each case changes one parameter (or a Kirchhoff-linked pair for emissivity)
while all other inputs stay at the baseline. Metrics are min, max, and final
temperature over five orbits, plus differences from the baseline.

This studies sensitivity of the teaching model. It is not experimental
validation against flight data.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from satellite_thermal.albedo import AlbedoParameters
from satellite_thermal.earth_infrared import EarthInfraredParameters
from satellite_thermal.orbit import CircularOrbit
from satellite_thermal.orbital_simulation import (
    OrbitalThermalResult,
    simulate_orbital_eclipse,
)
from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.validation import require_positive


@dataclass(frozen=True)
class SensitivityCase:
    """One sensitivity run definition."""

    case_id: str
    group: str
    label: str
    thermal: Phase1Parameters
    orbit: CircularOrbit
    earth_infrared: EarthInfraredParameters
    albedo: AlbedoParameters = AlbedoParameters()


@dataclass(frozen=True)
class SensitivityMetrics:
    """Temperature metrics for one completed sensitivity case."""

    case_id: str
    group: str
    label: str
    initial_k: float
    minimum_k: float
    maximum_k: float
    final_k: float
    delta_minimum_k: float
    delta_maximum_k: float
    delta_final_k: float
    result: OrbitalThermalResult


def baseline_case() -> SensitivityCase:
    """Phase 3B baseline inputs."""
    thermal = Phase1Parameters().validated()
    return SensitivityCase(
        case_id="baseline",
        group="baseline",
        label="Baseline (Phase 3B defaults)",
        thermal=thermal,
        orbit=CircularOrbit().validated(),
        earth_infrared=EarthInfraredParameters(
            infrared_absorptivity=thermal.emissivity
        ).validated(),
        albedo=AlbedoParameters().validated(),
    )


def build_sensitivity_cases() -> tuple[SensitivityCase, ...]:
    """Baseline plus one-at-a-time perturbations."""
    base = baseline_case()
    thermal0 = base.thermal
    cases: list[SensitivityCase] = [base]

    for alpha in (0.40, 0.80):
        cases.append(
            SensitivityCase(
                case_id=f"alpha_{alpha:.2f}",
                group="absorptivity",
                label=f"alpha = {alpha:.2f}",
                thermal=replace(thermal0, absorptivity=alpha).validated(),
                orbit=base.orbit,
                earth_infrared=base.earth_infrared,
                albedo=base.albedo,
            )
        )

    for epsilon in (0.60, 1.00):
        # Kirchhoff: infrared absorptivity tracks emissivity.
        cases.append(
            SensitivityCase(
                case_id=f"epsilon_{epsilon:.2f}",
                group="emissivity",
                label=f"epsilon = alpha_ir = {epsilon:.2f}",
                thermal=replace(thermal0, emissivity=epsilon).validated(),
                orbit=base.orbit,
                earth_infrared=replace(
                    base.earth_infrared, infrared_absorptivity=epsilon
                ).validated(),
                albedo=base.albedo,
            )
        )

    for power_w in (0.0, 10.0):
        cases.append(
            SensitivityCase(
                case_id=f"qint_{power_w:.0f}",
                group="internal_power",
                label=f"Q_internal = {power_w:.0f} W",
                thermal=replace(thermal0, internal_heat_w=power_w).validated(),
                orbit=base.orbit,
                earth_infrared=base.earth_infrared,
                albedo=base.albedo,
            )
        )

    for scale, tag in ((0.5, "0.5x"), (2.0, "2x")):
        cases.append(
            SensitivityCase(
                case_id=f"mass_{tag}",
                group="capacitance",
                label=f"mass = {tag} baseline ({thermal0.mass_kg * scale:.1f} kg)",
                thermal=replace(
                    thermal0, mass_kg=thermal0.mass_kg * scale
                ).validated(),
                orbit=base.orbit,
                earth_infrared=base.earth_infrared,
                albedo=base.albedo,
            )
        )

    for area in (0.04, 0.08):
        cases.append(
            SensitivityCase(
                case_id=f"arad_{area:.2f}",
                group="radiating_area",
                label=f"A_radiating = {area:.2f} m^2",
                thermal=replace(thermal0, radiating_area_m2=area).validated(),
                orbit=base.orbit,
                earth_infrared=base.earth_infrared,
                albedo=base.albedo,
            )
        )

    for altitude_km in (400.0, 600.0):
        cases.append(
            SensitivityCase(
                case_id=f"alt_{altitude_km:.0f}km",
                group="altitude",
                label=f"altitude = {altitude_km:.0f} km",
                thermal=base.thermal,
                orbit=replace(
                    base.orbit, altitude_m=altitude_km * 1000.0
                ).validated(),
                earth_infrared=base.earth_infrared,
                albedo=base.albedo,
            )
        )

    return tuple(cases)


def run_sensitivity_case(
    case: SensitivityCase,
    orbit_count: int = 5,
    time_step_s: float = 1.0,
) -> OrbitalThermalResult:
    """Integrate one sensitivity case with Earth IR and albedo enabled."""
    require_positive("time_step_s", time_step_s)
    return simulate_orbital_eclipse(
        orbit_count=orbit_count,
        time_step_s=time_step_s,
        parameters=case.thermal,
        orbit=case.orbit,
        include_earth_infrared=True,
        earth_infrared=case.earth_infrared,
        include_albedo=True,
        albedo=case.albedo,
    )


def metrics_from_result(
    case: SensitivityCase,
    result: OrbitalThermalResult,
    baseline: OrbitalThermalResult,
) -> SensitivityMetrics:
    """Build metrics relative to a baseline history."""
    minimum_k = min(result.temperature_k)
    maximum_k = max(result.temperature_k)
    final_k = result.temperature_k[-1]
    base_min = min(baseline.temperature_k)
    base_max = max(baseline.temperature_k)
    base_final = baseline.temperature_k[-1]
    return SensitivityMetrics(
        case_id=case.case_id,
        group=case.group,
        label=case.label,
        initial_k=result.temperature_k[0],
        minimum_k=minimum_k,
        maximum_k=maximum_k,
        final_k=final_k,
        delta_minimum_k=minimum_k - base_min,
        delta_maximum_k=maximum_k - base_max,
        delta_final_k=final_k - base_final,
        result=result,
    )


def run_sensitivity_study(
    orbit_count: int = 5,
    time_step_s: float = 1.0,
    cases: tuple[SensitivityCase, ...] | None = None,
) -> tuple[SensitivityMetrics, ...]:
    """Run the full sensitivity set and return metrics ordered as defined."""
    study_cases = cases or build_sensitivity_cases()
    if not study_cases:
        raise ValueError("At least one sensitivity case is required.")
    if study_cases[0].case_id != "baseline":
        raise ValueError("The first sensitivity case must be the baseline.")

    results: list[SensitivityMetrics] = []
    baseline_result: OrbitalThermalResult | None = None
    for case in study_cases:
        result = run_sensitivity_case(case, orbit_count, time_step_s)
        if baseline_result is None:
            baseline_result = result
        results.append(metrics_from_result(case, result, baseline_result))
    return tuple(results)


def cases_in_group(
    metrics: tuple[SensitivityMetrics, ...],
    group: str,
) -> tuple[SensitivityMetrics, ...]:
    """Return baseline plus every case in the named group."""
    baseline = [item for item in metrics if item.case_id == "baseline"]
    selected = [item for item in metrics if item.group == group]
    if not baseline:
        raise ValueError("Baseline metrics are missing.")
    return (baseline[0], *selected)
