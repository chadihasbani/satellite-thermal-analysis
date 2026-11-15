"""Hot / nominal / cold thermal screening scenario presets.

Modelling convention (Checkpoint 4)
-----------------------------------
Two common LEO screening conventions appear in the literature:

1. **Energy-balance orbit-average triples** (NASA Preferred Practice
   GD-AP-2301 / PD-ED-1201 style): choose seasonal solar irradiance and a
   paired Bond albedo, then set Earth OLR from
   ``E_olr = (1 - a) * S / 4`` so the planetary mean energy balance stays
   consistent. Under that pairing, the cold albedo case has a *higher*
   OLR than the hot albedo case — not an independent stack of every
   extreme.

2. **Statistically paired albedo/OLR extremes** (ERBE / STEM /
   SSP-30425 / mission NEDD tables): hot and cold albedo–OLR pairs are
   selected for a given inclination and thermal time constant because the
   absolute maximum albedo and maximum OLR do not occur together. Example
   ISS-oriented pairs quoted in Orion passive-thermal overviews use roughly
   S≈1414 W/m², a≈0.28, OLR≈258 W/m² (hot) versus S≈1322 W/m², a≈0.17,
   OLR≈217 W/m² (cold).

This educational single-node model uses constant planetary albedo and OLR
over an orbit (Version 1.0 effective-area Earth loads). Convention (1) is
therefore the better match: Hot/Cold environmental fluxes follow GD-AP-2301
winter/summer solar values with the practice’s hot/cold albedo factors and
energy-balance OLR. Convention (2) is documented as an alternative and is
**not** used for the presets.

GD-AP-2301 Table 1 values are intended for **orbit-average** screening
analyses. Here they are applied as **simplified constant** environmental
parameters for the entire simulation (same S, a, and E_olr at every time
step), which matches this repository’s constant-load Earth IR / albedo model
but is not a full orbit-average heat-rate integrator.

The **Nominal** environmental fluxes remain this repository’s Version 1.0
educational defaults (S = 1361 W/m², a = 0.30, E_olr = 240 W/m²) so legacy
baselines stay bit-reproducible. Those nominal numbers are close to, but
not identical to, the GD-AP-2301 nominal table entry (1368 / 0.30 / 239).

Presets are **screening scenarios**, not universal spacecraft worst cases.
Geometry and coating properties stay under user control unless the user
edits them. Optical end-of-life degradation (ECSS hot-case practice) is
intentionally **not** folded into these presets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from satellite_thermal.internal_power import (
    ILLUSTRATIVE_HIGH_POWER_W,
    ILLUSTRATIVE_NOMINAL_W,
    ILLUSTRATIVE_STANDBY_W,
    PowerScheduleKind,
)
from satellite_thermal.orbit import CircularOrbit, critical_beta_rad
from satellite_thermal.validation import require_finite_number, require_positive


class ThermalScenarioId(str, Enum):
    """GUI / API identifiers for thermal screening presets."""

    NOMINAL = "nominal"
    HOT = "hot"
    COLD = "cold"
    CUSTOM = "custom"


# NASA Preferred Practice GD-AP-2301 seasonal solar constants (W/m²).
NASA_PP_SOLAR_WINTER_W_PER_M2 = 1422.0
NASA_PP_SOLAR_SUMMER_W_PER_M2 = 1318.0
NASA_PP_SOLAR_NOMINAL_W_PER_M2 = 1367.5

# GD-AP-2301 recommended albedo factors for hot / nominal / cold programs.
NASA_PP_ALBEDO_HOT = 0.35
NASA_PP_ALBEDO_NOMINAL = 0.30
NASA_PP_ALBEDO_COLD = 0.25

# Repository Version 1.0 educational environmental defaults (Nominal preset).
REPO_NOMINAL_SOLAR_W_PER_M2 = 1361.0
REPO_NOMINAL_ALBEDO = 0.30
REPO_NOMINAL_OLR_W_PER_M2 = 240.0

SCENARIO_CASE_NOMINAL = "Nominal"
SCENARIO_CASE_HOT = "Hot screening"
SCENARIO_CASE_COLD = "Cold screening"
SCENARIO_CASE_NAMES = (SCENARIO_CASE_COLD, SCENARIO_CASE_NOMINAL, SCENARIO_CASE_HOT)


def parse_thermal_scenario_id(value: str | ThermalScenarioId) -> ThermalScenarioId:
    """Parse a scenario identifier string."""
    if isinstance(value, ThermalScenarioId):
        return value
    normalized = str(value).strip().lower()
    try:
        return ThermalScenarioId(normalized)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in ThermalScenarioId)
        raise ValueError(
            f"thermal scenario must be one of: {allowed}. Got {value!r}."
        ) from exc


def earth_olr_energy_balance_w_per_m2(
    solar_flux_w_per_m2: float,
    earth_bond_albedo: float,
) -> float:
    """Planet-mean OLR from ``E = (1 − a) S / 4`` (GD-AP-2301)."""
    solar = require_positive("solar_flux_w_per_m2", solar_flux_w_per_m2)
    albedo = require_finite_number("earth_bond_albedo", earth_bond_albedo)
    if not 0.0 <= albedo <= 1.0:
        raise ValueError("earth_bond_albedo must be between 0 and 1.")
    return (1.0 - albedo) * solar / 4.0


def hot_case_beta_deg(altitude_km: float) -> float:
    """Beta just above cylindrical critical beta (continuous sunlight).

    This orbital choice is an **illustrative screening assumption** for a
    high-solar-exposure LEO pass with no eclipse, not a NASA-mandated beta.
    """
    altitude_m = require_positive("altitude_km", altitude_km) * 1000.0
    beta_c_deg = math.degrees(critical_beta_rad(CircularOrbit(altitude_m=altitude_m)))
    return min(90.0, float(math.ceil(beta_c_deg) + 1.0))


@dataclass(frozen=True)
class ThermalScenarioDefinition:
    """Explicit environmental and operational overlays for one preset."""

    scenario_id: ThermalScenarioId
    display_name: str
    summary: str
    # Environmental
    solar_flux_w_per_m2: float
    earth_bond_albedo: float
    earth_olr_w_per_m2: float
    beta_deg: float
    include_earth_infrared: bool
    include_albedo: bool
    # Operational (kept separate from environmental fluxes)
    power_schedule_kind: str
    internal_heat_w: float
    solar_source_note: str
    albedo_source_note: str
    olr_source_note: str
    beta_source_note: str
    power_source_note: str

    def parameter_rows(self) -> list[dict[str, object]]:
        """Table rows for GUI / documentation display."""
        return [
            {
                "Category": "Environmental",
                "Parameter": "Solar irradiance S",
                "Value": self.solar_flux_w_per_m2,
                "Units": "W/m²",
                "Notes": self.solar_source_note,
            },
            {
                "Category": "Environmental",
                "Parameter": "Earth Bond albedo a",
                "Value": self.earth_bond_albedo,
                "Units": "—",
                "Notes": self.albedo_source_note,
            },
            {
                "Category": "Environmental",
                "Parameter": "Earth OLR E_olr",
                "Value": round(self.earth_olr_w_per_m2, 3),
                "Units": "W/m²",
                "Notes": self.olr_source_note,
            },
            {
                "Category": "Environmental",
                "Parameter": "Orbital beta β",
                "Value": self.beta_deg,
                "Units": "°",
                "Notes": self.beta_source_note,
            },
            {
                "Category": "Environmental",
                "Parameter": "Earth IR / albedo loads",
                "Value": (
                    "both on"
                    if self.include_earth_infrared and self.include_albedo
                    else "see flags"
                ),
                "Units": "—",
                "Notes": "Screening cases include both planetary loads.",
            },
            {
                "Category": "Operational",
                "Parameter": "Internal power schedule",
                "Value": self.power_schedule_kind,
                "Units": "—",
                "Notes": self.power_source_note,
            },
            {
                "Category": "Operational",
                "Parameter": "Constant internal heat",
                "Value": self.internal_heat_w,
                "Units": "W",
                "Notes": self.power_source_note,
            },
        ]


def build_scenario_definition(
    scenario_id: str | ThermalScenarioId,
    altitude_km: float = 500.0,
) -> ThermalScenarioDefinition:
    """Build a fully resolved scenario definition for the given altitude."""
    kind = parse_thermal_scenario_id(scenario_id)
    if kind is ThermalScenarioId.CUSTOM:
        raise ValueError("Custom scenario has no fixed parameter table.")

    if kind is ThermalScenarioId.NOMINAL:
        return ThermalScenarioDefinition(
            scenario_id=kind,
            display_name=SCENARIO_CASE_NOMINAL,
            summary=(
                "Version 1.0 educational environmental defaults with β = 0° "
                "and constant illustrative nominal internal power."
            ),
            solar_flux_w_per_m2=REPO_NOMINAL_SOLAR_W_PER_M2,
            earth_bond_albedo=REPO_NOMINAL_ALBEDO,
            earth_olr_w_per_m2=REPO_NOMINAL_OLR_W_PER_M2,
            beta_deg=0.0,
            include_earth_infrared=True,
            include_albedo=True,
            power_schedule_kind=PowerScheduleKind.CONSTANT.value,
            internal_heat_w=ILLUSTRATIVE_NOMINAL_W,
            solar_source_note="Repo V1 educational default (not GD-AP-2301 1367.5).",
            albedo_source_note="Repo V1 / GD-AP-2301 nominal albedo factor 0.30.",
            olr_source_note="Repo V1 educational default 240 W/m².",
            beta_source_note="V1 reference: maximum cylindrical eclipse (β = 0°).",
            power_source_note=(
                f"Illustrative constant {ILLUSTRATIVE_NOMINAL_W:g} W "
                "(not a published EPS budget)."
            ),
        )

    if kind is ThermalScenarioId.HOT:
        solar = NASA_PP_SOLAR_WINTER_W_PER_M2
        albedo = NASA_PP_ALBEDO_HOT
        olr = earth_olr_energy_balance_w_per_m2(solar, albedo)
        beta = hot_case_beta_deg(altitude_km)
        return ThermalScenarioDefinition(
            scenario_id=kind,
            display_name=SCENARIO_CASE_HOT,
            summary=(
                "GD-AP-2301 winter solar + hot albedo with energy-balance OLR, "
                "continuous-sunlight beta, and illustrative high internal power."
            ),
            solar_flux_w_per_m2=solar,
            earth_bond_albedo=albedo,
            earth_olr_w_per_m2=olr,
            beta_deg=beta,
            include_earth_infrared=True,
            include_albedo=True,
            power_schedule_kind=PowerScheduleKind.CONSTANT.value,
            internal_heat_w=ILLUSTRATIVE_HIGH_POWER_W,
            solar_source_note="NASA GD-AP-2301 winter solstice solar 1422 W/m².",
            albedo_source_note="NASA GD-AP-2301 hot-case albedo factor 0.35.",
            olr_source_note="Derived: E_olr = (1 − a) S / 4 (GD-AP-2301).",
            beta_source_note=(
                "Illustrative: β just above critical beta at this altitude "
                "(continuous sunlight)."
            ),
            power_source_note=(
                f"Illustrative constant {ILLUSTRATIVE_HIGH_POWER_W:g} W "
                "(ECSS-style high dissipation assumption; not EOL coatings)."
            ),
        )

    solar = NASA_PP_SOLAR_SUMMER_W_PER_M2
    albedo = NASA_PP_ALBEDO_COLD
    olr = earth_olr_energy_balance_w_per_m2(solar, albedo)
    return ThermalScenarioDefinition(
        scenario_id=kind,
        display_name=SCENARIO_CASE_COLD,
        summary=(
            "GD-AP-2301 summer solar + cold albedo with energy-balance OLR, "
            "β = 0° (long eclipse), and illustrative standby internal power."
        ),
        solar_flux_w_per_m2=solar,
        earth_bond_albedo=albedo,
        earth_olr_w_per_m2=olr,
        beta_deg=0.0,
        include_earth_infrared=True,
        include_albedo=True,
        power_schedule_kind=PowerScheduleKind.CONSTANT.value,
        internal_heat_w=ILLUSTRATIVE_STANDBY_W,
        solar_source_note="NASA GD-AP-2301 summer solstice solar 1318 W/m².",
        albedo_source_note="NASA GD-AP-2301 cold-case albedo factor 0.25.",
        olr_source_note=(
            "Derived: E_olr = (1 − a) S / 4. Energy-balance cold OLR exceeds "
            "hot OLR; eclipse and lower solar still cool the craft."
        ),
        beta_source_note="Illustrative screening: β = 0° for maximum eclipse.",
        power_source_note=(
            f"Illustrative constant {ILLUSTRATIVE_STANDBY_W:g} W "
            "(ECSS-style low dissipation assumption)."
        ),
    )


def scenario_overlay_fields(definition: ThermalScenarioDefinition) -> dict[str, object]:
    """Fields a non-custom scenario writes onto a GUI request mapping."""
    return {
        "solar_flux_w_per_m2": definition.solar_flux_w_per_m2,
        "earth_bond_albedo": definition.earth_bond_albedo,
        "earth_olr_w_per_m2": definition.earth_olr_w_per_m2,
        "beta_deg": definition.beta_deg,
        "include_earth_infrared": definition.include_earth_infrared,
        "include_albedo": definition.include_albedo,
        "power_schedule_kind": definition.power_schedule_kind,
        "internal_heat_w": definition.internal_heat_w,
    }


def scenario_controlled_field_names() -> tuple[str, ...]:
    """Request field names owned by non-custom scenario presets."""
    sample = build_scenario_definition(ThermalScenarioId.NOMINAL)
    return tuple(scenario_overlay_fields(sample).keys())


def scenario_select_options() -> list[tuple[str, str]]:
    """(id, label) pairs for the GUI selector (plain-language names)."""
    return [
        (ThermalScenarioId.CUSTOM.value, "Custom"),
        (ThermalScenarioId.NOMINAL.value, "Normal conditions"),
        (ThermalScenarioId.HOT.value, "Hot conditions"),
        (ThermalScenarioId.COLD.value, "Cold conditions"),
    ]


def sync_session_values_from_scenario(
    scenario_id: str | ThermalScenarioId,
    altitude_km: float,
) -> dict[str, object]:
    """Session-state updates for sidebar widgets when a preset is chosen."""
    kind = parse_thermal_scenario_id(scenario_id)
    if kind is ThermalScenarioId.CUSTOM:
        return {}
    definition = build_scenario_definition(kind, altitude_km=altitude_km)
    return {
        f"gui_{name}": value
        for name, value in scenario_overlay_fields(definition).items()
    }


def preset_controls_locked(
    scenario_id: str | ThermalScenarioId,
    mode: str | None = None,
) -> bool:
    """True when preset-owned widgets must not be user-editable."""
    if mode == "scenario_compare":
        return True
    return parse_thermal_scenario_id(scenario_id) is not ThermalScenarioId.CUSTOM


def mismatched_preset_field_names(
    field_values: dict[str, object],
    scenario_id: str | ThermalScenarioId,
    altitude_km: float,
    *,
    rel_tol: float = 0.0,
    abs_tol: float = 1e-9,
) -> tuple[str, ...]:
    """Return overlay fields that disagree with the active non-custom preset.

    ``field_values`` maps bare ``GuiRunRequest`` field names (no ``gui_``
    prefix) to the values shown in the GUI / session state. Custom scenarios
    never report mismatches — sidebar values are authoritative.
    """
    kind = parse_thermal_scenario_id(scenario_id)
    if kind is ThermalScenarioId.CUSTOM:
        return ()
    expected = scenario_overlay_fields(
        build_scenario_definition(kind, altitude_km=altitude_km)
    )
    mismatches: list[str] = []
    for name, expected_value in expected.items():
        if name not in field_values:
            mismatches.append(name)
            continue
        actual = field_values[name]
        if isinstance(expected_value, bool) or isinstance(expected_value, str):
            if actual != expected_value:
                mismatches.append(name)
            continue
        if isinstance(expected_value, (int, float)):
            try:
                actual_number = float(actual)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                mismatches.append(name)
                continue
            if not math.isclose(
                actual_number,
                float(expected_value),
                rel_tol=rel_tol,
                abs_tol=abs_tol,
            ):
                mismatches.append(name)
            continue
        if actual != expected_value:
            mismatches.append(name)
    return tuple(mismatches)
