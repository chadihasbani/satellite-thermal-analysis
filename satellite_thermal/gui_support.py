"""Helpers for the Streamlit GUI.

These functions only assemble existing model inputs and plots. They do not
re-implement the thermal equations.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from satellite_thermal.albedo import AlbedoParameters
from satellite_thermal.attitude import AttitudeMode, parse_attitude_mode
from satellite_thermal.earth_infrared import EarthInfraredParameters
from satellite_thermal.internal_power import (
    ILLUSTRATIVE_HIGH_POWER_W,
    ILLUSTRATIVE_NOMINAL_W,
    ILLUSTRATIVE_STANDBY_W,
    InternalPowerSchedule,
    OperatingModePowers,
    PowerInterval,
    PowerScheduleKind,
    parse_power_schedule_kind,
)
from satellite_thermal.orbit import CircularOrbit, orbital_period_s
from satellite_thermal.orbital_simulation import (
    THERMAL_MODEL_ENHANCED,
    THERMAL_MODEL_LEGACY,
    OrbitalThermalResult,
    eclipse_intervals_s,
    parse_thermal_model,
    simulate_orbital_eclipse,
)
from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.spacecraft_geometry import RectangularBusGeometry
from satellite_thermal.units import kelvin_to_celsius
from satellite_thermal.validation import require_positive

# Soft cap so the GUI stays responsive for interactive runs.
# Includes nominal Euler samples plus scheduled power-event splits.
MAX_GUI_SAMPLES = 250_000
ABSOLUTE_ZERO_C = -273.15


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
    beta_deg: float
    orbit_count: int
    time_step_s: float
    include_earth_infrared: bool
    include_albedo: bool
    thermal_model: str = THERMAL_MODEL_LEGACY
    attitude_mode: str = AttitudeMode.FIXED_INERTIAL.value
    body_length_m: float = 0.1
    body_width_m: float = 0.1
    body_height_m: float = 0.1
    power_schedule_kind: str = PowerScheduleKind.CONSTANT.value
    standby_power_w: float = ILLUSTRATIVE_STANDBY_W
    nominal_power_w: float = ILLUSTRATIVE_NOMINAL_W
    high_power_w: float = ILLUSTRATIVE_HIGH_POWER_W
    periodic_period_s: float = 600.0
    periodic_high_duration_s: float = 120.0
    custom_intervals_text: str = ""


def default_gui_request() -> GuiRunRequest:
    """Defaults matching the default reference case (Earth IR + albedo on)."""
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
        beta_deg=0.0,
        orbit_count=5,
        time_step_s=5.0,
        include_earth_infrared=True,
        include_albedo=True,
        thermal_model=THERMAL_MODEL_LEGACY,
        attitude_mode=AttitudeMode.FIXED_INERTIAL.value,
        body_length_m=0.1,
        body_width_m=0.1,
        body_height_m=0.1,
        power_schedule_kind=PowerScheduleKind.CONSTANT.value,
        standby_power_w=ILLUSTRATIVE_STANDBY_W,
        nominal_power_w=ILLUSTRATIVE_NOMINAL_W,
        high_power_w=ILLUSTRATIVE_HIGH_POWER_W,
        periodic_period_s=600.0,
        periodic_high_duration_s=120.0,
        custom_intervals_text="",
    )


def geometry_from_request(request: GuiRunRequest) -> RectangularBusGeometry:
    """Build validated bus geometry from GUI dimensions and optics."""
    return RectangularBusGeometry(
        length_m=request.body_length_m,
        width_m=request.body_width_m,
        height_m=request.body_height_m,
        absorptivity=request.absorptivity,
        emissivity=request.emissivity,
    ).validated()


def parse_custom_intervals_text(text: str) -> tuple[PowerInterval, ...]:
    """Parse ``start,end,power`` rows separated by ``;`` or newlines."""
    raw = str(text).strip()
    if not raw:
        return ()
    chunks = []
    for part in raw.replace("\n", ";").split(";"):
        piece = part.strip()
        if piece:
            chunks.append(piece)
    intervals: list[PowerInterval] = []
    for index, chunk in enumerate(chunks):
        fields = [item.strip() for item in chunk.split(",")]
        if len(fields) != 3:
            raise ValueError(
                "Each custom interval must be 'start_s,end_s,power_w'. "
                f"Bad entry #{index + 1}: {chunk!r}."
            )
        intervals.append(
            PowerInterval(
                start_s=float(fields[0]),
                end_s=float(fields[1]),
                power_w=float(fields[2]),
                label=f"interval_{index + 1}",
            )
        )
    return tuple(intervals)


def power_schedule_from_request(request: GuiRunRequest) -> InternalPowerSchedule:
    """Build the validated internal-power schedule from GUI fields."""
    kind = parse_power_schedule_kind(request.power_schedule_kind)
    mode_powers = OperatingModePowers(
        standby_w=request.standby_power_w,
        nominal_w=request.nominal_power_w,
        high_power_w=request.high_power_w,
    ).validated()
    if kind is PowerScheduleKind.CONSTANT:
        return InternalPowerSchedule(
            kind=kind.value,
            constant_power_w=request.internal_heat_w,
        ).validated()
    if kind is PowerScheduleKind.ECLIPSE_REDUCED:
        return InternalPowerSchedule(
            kind=kind.value,
            sunlight_power_w=mode_powers.nominal_w,
            eclipse_power_w=mode_powers.standby_w,
            constant_power_w=request.internal_heat_w,
        ).validated()
    if kind is PowerScheduleKind.PERIODIC_HIGH:
        return InternalPowerSchedule(
            kind=kind.value,
            base_power_w=mode_powers.nominal_w,
            high_power_w=mode_powers.high_power_w,
            period_s=request.periodic_period_s,
            high_duration_s=request.periodic_high_duration_s,
            constant_power_w=request.internal_heat_w,
        ).validated()
    return InternalPowerSchedule(
        kind=PowerScheduleKind.CUSTOM_INTERVALS.value,
        constant_power_w=request.internal_heat_w,
        intervals=parse_custom_intervals_text(request.custom_intervals_text),
    ).validated()


def count_scheduled_power_events(
    schedule: InternalPowerSchedule,
    duration_s: float,
) -> int:
    """Upper-bound count of schedule discontinuities in ``(0, duration_s)``.

    Used for GUI sample estimation. ``constant`` and ``eclipse_reduced``
    contribute zero schedule events (eclipse edges remain step-sampled).
    """
    settings = schedule.validated()
    duration = require_positive("duration_s", duration_s)
    kind = parse_power_schedule_kind(settings.kind)
    if kind in (PowerScheduleKind.CONSTANT, PowerScheduleKind.ECLIPSE_REDUCED):
        return 0
    if kind is PowerScheduleKind.PERIODIC_HIGH:
        if settings.high_duration_s <= 0.0 or settings.high_duration_s >= settings.period_s:
            return 0
        # At most two events per period (high start and high end).
        periods = math.ceil(duration / settings.period_s)
        return int(2 * periods)
    edges: set[float] = set()
    for interval in settings.intervals:
        if 0.0 < interval.start_s < duration:
            edges.add(interval.start_s)
        if 0.0 < interval.end_s < duration:
            edges.add(interval.end_s)
    return len(edges)


def estimate_gui_sample_count(request: GuiRunRequest) -> int:
    """Conservative sample-count estimate including power-event splits."""
    orbit = CircularOrbit(
        altitude_m=request.altitude_km * 1000.0,
        beta_rad=math.radians(request.beta_deg),
    ).validated()
    duration_s = request.orbit_count * orbital_period_s(orbit)
    # Nominal Euler samples, plus a small margin for the final instant.
    base_samples = int(math.floor(duration_s / request.time_step_s)) + 2
    schedule = power_schedule_from_request(request)
    event_samples = count_scheduled_power_events(schedule, duration_s)
    return base_samples + event_samples


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
    orbit = CircularOrbit(
        altitude_m=request.altitude_km * 1000.0,
        beta_rad=math.radians(request.beta_deg),
    ).validated()
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


def validate_gui_request(request: GuiRunRequest) -> GuiRunRequest:
    """Validate GUI inputs before solving. Raises ValueError on bad input."""
    values = asdict(request)
    for name, value in values.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and not math.isfinite(float(value)):
            raise ValueError(f"{name} must be a finite number.")

    if isinstance(request.orbit_count, bool) or not isinstance(request.orbit_count, int):
        raise ValueError("orbit_count must be an integer.")
    if request.orbit_count <= 0:
        raise ValueError("orbit_count must be greater than 0.")
    require_positive("time_step_s", request.time_step_s)
    if request.initial_temperature_c <= ABSOLUTE_ZERO_C:
        raise ValueError(
            "initial_temperature_c must be above absolute zero "
            f"({ABSOLUTE_ZERO_C} °C)."
        )
    if request.internal_heat_w < 0.0:
        raise ValueError(
            "internal_heat_w must be >= 0 W in this GUI "
            "(onboard dissipation only; external cooling sinks are not modelled)."
        )
    if request.mass_kg <= 0.0:
        raise ValueError("mass_kg must be greater than 0.")
    if request.specific_heat_j_per_kg_k <= 0.0:
        raise ValueError("specific_heat_j_per_kg_k must be greater than 0.")
    for area_name in (
        "projected_area_m2",
        "radiating_area_m2",
        "earth_facing_area_m2",
        "albedo_area_m2",
    ):
        if getattr(request, area_name) <= 0.0:
            raise ValueError(f"{area_name} must be greater than 0.")
    if not 0.0 <= request.absorptivity <= 1.0:
        raise ValueError("absorptivity must be between 0 and 1.")
    if not 0.0 <= request.emissivity <= 1.0:
        raise ValueError("emissivity must be between 0 and 1.")
    if not 0.0 <= request.earth_bond_albedo <= 1.0:
        raise ValueError("earth_bond_albedo must be between 0 and 1.")
    if request.solar_flux_w_per_m2 < 0.0:
        raise ValueError("solar_flux_w_per_m2 must be >= 0.")
    if request.earth_olr_w_per_m2 < 0.0:
        raise ValueError("earth_olr_w_per_m2 must be >= 0.")
    if request.altitude_km <= 0.0:
        raise ValueError("altitude_km must be greater than 0.")
    if abs(request.beta_deg) > 90.0:
        raise ValueError("beta_deg must be between -90 and 90 degrees.")
    parse_thermal_model(request.thermal_model)
    parse_attitude_mode(request.attitude_mode)
    for dim_name in ("body_length_m", "body_width_m", "body_height_m"):
        if getattr(request, dim_name) <= 0.0:
            raise ValueError(f"{dim_name} must be greater than 0.")
    for power_name in ("standby_power_w", "nominal_power_w", "high_power_w"):
        if getattr(request, power_name) < 0.0:
            raise ValueError(f"{power_name} must be >= 0.")
    if request.periodic_period_s <= 0.0:
        raise ValueError("periodic_period_s must be greater than 0.")
    if request.periodic_high_duration_s < 0.0:
        raise ValueError("periodic_high_duration_s must be >= 0.")
    # Validate schedule construction (overlaps, kinds, etc.).
    power_schedule_from_request(request)

    # Include scheduled power-event splits in the interactive sample budget.
    estimated_samples = estimate_gui_sample_count(request)
    if estimated_samples > MAX_GUI_SAMPLES:
        raise ValueError(
            "Requested run is too large for interactive use "
            f"(~{estimated_samples:,} samples including power-event splits; "
            f"limit {MAX_GUI_SAMPLES:,}). "
            "Increase the time step, reduce the number of orbits, lengthen the "
            "periodic period, or reduce custom power intervals. "
            "The GUI does not silently truncate incomplete runs."
        )
    return request


def clamp_sample_index(n_samples: int, index: int) -> int:
    """Clamp a sample index into ``[0, n_samples - 1]``."""
    if isinstance(n_samples, bool) or not isinstance(n_samples, int) or n_samples <= 0:
        raise ValueError(f"n_samples must be a positive integer, got {n_samples!r}.")
    if isinstance(index, bool) or not isinstance(index, int):
        raise ValueError(f"index must be an integer, got {index!r}.")
    return max(0, min(index, n_samples - 1))


def request_fingerprint(mode: str, request: GuiRunRequest) -> tuple:
    """Hashable snapshot of the inputs that produced a displayed study."""
    return (mode, tuple(sorted(asdict(request).items())))


def run_gui_simulation(request: GuiRunRequest) -> OrbitalThermalResult:
    """Run the orbital solver from a GUI request (legacy or enhanced)."""
    validate_gui_request(request)
    thermal, orbit, earth_ir, albedo = build_model_inputs(request)
    model = parse_thermal_model(request.thermal_model)
    geometry = (
        geometry_from_request(request)
        if model == THERMAL_MODEL_ENHANCED
        else None
    )
    return simulate_orbital_eclipse(
        orbit_count=request.orbit_count,
        time_step_s=request.time_step_s,
        parameters=thermal,
        orbit=orbit,
        include_earth_infrared=request.include_earth_infrared,
        earth_infrared=earth_ir,
        include_albedo=request.include_albedo,
        albedo=albedo,
        thermal_model=model,
        geometry=geometry,
        attitude_mode=request.attitude_mode,
        power_schedule=power_schedule_from_request(request),
        max_samples=MAX_GUI_SAMPLES,
    )


def temperature_metrics_c(result: OrbitalThermalResult) -> dict[str, float]:
    """Initial, minimum, maximum, and final temperatures in Celsius."""
    return {
        "initial_c": kelvin_to_celsius(result.temperature_k[0]),
        "minimum_c": kelvin_to_celsius(min(result.temperature_k)),
        "maximum_c": kelvin_to_celsius(max(result.temperature_k)),
        "final_c": kelvin_to_celsius(result.temperature_k[-1]),
    }


@dataclass(frozen=True)
class NamedResult:
    """A labeled simulation history for comparison plots."""

    name: str
    request: GuiRunRequest
    result: OrbitalThermalResult
    thermal: Phase1Parameters
    orbit: CircularOrbit
    earth_infrared: EarthInfraredParameters
    albedo: AlbedoParameters


@dataclass(frozen=True)
class CompletedGuiStudy:
    """Persisted GUI study: one or more runs from a single explicit solve."""

    mode: str
    primary: NamedResult
    companions: tuple[NamedResult, ...] = ()
    changed_fields: tuple[str, ...] = ()


# Stable display names for environmental-heating cases (Mode 3).
ENV_CASE_A = "A - No Earth Heating"
ENV_CASE_B = "B - With Earth Infrared"
ENV_CASE_C = "C - With Earth Infrared and Albedo"
ENV_CASE_NAMES = (ENV_CASE_A, ENV_CASE_B, ENV_CASE_C)

REF_CASE_NAME = "Reference"
MOD_CASE_NAME = "Modified"
SINGLE_CASE_NAME = "Single simulation"

_PARAMETER_LABELS = {
    "mass_kg": "Mass (kg)",
    "specific_heat_j_per_kg_k": "Specific heat cp (J/(kg·K))",
    "initial_temperature_c": "Initial temperature (°C)",
    "absorptivity": "Solar absorptivity α",
    "emissivity": "Infrared emissivity ε",
    "projected_area_m2": "Projected solar area (m²)",
    "radiating_area_m2": "Radiating area (m²)",
    "earth_facing_area_m2": "Earth-facing area (m²)",
    "albedo_area_m2": "Albedo area (m²)",
    "internal_heat_w": "Internal power (W)",
    "solar_flux_w_per_m2": "Solar flux S (W/m²)",
    "earth_olr_w_per_m2": "Earth OLR E_olr (W/m²)",
    "earth_bond_albedo": "Earth Bond albedo a",
    "altitude_km": "Altitude (km)",
    "beta_deg": "Orbital beta angle (°)",
    "orbit_count": "Number of orbits",
    "time_step_s": "Time step (s)",
    "include_earth_infrared": "Include Earth IR",
    "include_albedo": "Include albedo",
    "thermal_model": "Thermal model",
    "attitude_mode": "Attitude mode",
    "body_length_m": "Body length (m)",
    "body_width_m": "Body width (m)",
    "body_height_m": "Body height (m)",
    "power_schedule_kind": "Internal power schedule",
    "standby_power_w": "Standby power (W)",
    "nominal_power_w": "Nominal power (W)",
    "high_power_w": "High power (W)",
    "periodic_period_s": "Periodic high period (s)",
    "periodic_high_duration_s": "Periodic high duration (s)",
    "custom_intervals_text": "Custom power intervals",
}

_ENV_HEATING_LABELS = {
    ENV_CASE_A: "No Earth heating",
    ENV_CASE_B: "Earth infrared included",
    ENV_CASE_C: "Earth infrared + albedo",
}


def changed_parameter_labels(
    baseline: GuiRunRequest,
    modified: GuiRunRequest,
) -> tuple[str, ...]:
    """Human-readable list of fields that differ from baseline."""
    labels = []
    for field, label in _PARAMETER_LABELS.items():
        if getattr(baseline, field) != getattr(modified, field):
            labels.append(label)
    return tuple(labels)


def changed_parameter_rows(
    baseline: GuiRunRequest,
    modified: GuiRunRequest,
) -> list[dict[str, object]]:
    """Rows for a reference-vs-modified comparison table."""
    rows: list[dict[str, object]] = []
    for field, label in _PARAMETER_LABELS.items():
        base_value = getattr(baseline, field)
        mod_value = getattr(modified, field)
        if base_value != mod_value:
            rows.append(
                {
                    "Parameter": label,
                    "Reference": base_value,
                    "Modified": mod_value,
                }
            )
    return rows


def comparison_metrics_rows(curves: tuple[NamedResult, ...]) -> list[dict[str, object]]:
    """Temperature metric rows for comparison panels."""
    rows: list[dict[str, object]] = []
    for curve in curves:
        metrics = temperature_metrics_c(curve.result)
        rows.append(
            {
                "Case": curve.name,
                "Initial (°C)": round(metrics["initial_c"], 2),
                "Minimum (°C)": round(metrics["minimum_c"], 2),
                "Maximum (°C)": round(metrics["maximum_c"], 2),
                "Final (°C)": round(metrics["final_c"], 2),
                "Period (min)": round(curve.result.period_s / 60.0, 3),
            }
        )
    return rows


def environment_comparison_summary_rows(
    curves: tuple[NamedResult, ...],
) -> list[dict[str, object]]:
    """Readable A/B/C final-temperature summary with incremental differences."""
    if len(curves) != 3:
        raise ValueError("Environment summary requires exactly three curves (A, B, C).")
    finals = [temperature_metrics_c(curve.result)["final_c"] for curve in curves]
    return [
        {
            "Case": curves[0].name,
            "Environmental heating": _ENV_HEATING_LABELS.get(
                curves[0].name, "No Earth heating"
            ),
            "Final temperature (°C)": round(finals[0], 2),
            "Temperature change": "Reference",
        },
        {
            "Case": curves[1].name,
            "Environmental heating": _ENV_HEATING_LABELS.get(
                curves[1].name, "Earth infrared included"
            ),
            "Final temperature (°C)": round(finals[1], 2),
            "Temperature change": f"B − A = {finals[1] - finals[0]:+.2f} K",
        },
        {
            "Case": curves[2].name,
            "Environmental heating": _ENV_HEATING_LABELS.get(
                curves[2].name, "Earth infrared + albedo"
            ),
            "Final temperature (°C)": round(finals[2], 2),
            "Temperature change": f"C − B = {finals[2] - finals[1]:+.2f} K",
        },
    ]


def environment_comparison_interpretation(curves: tuple[NamedResult, ...]) -> str:
    """Short auto-generated interpretation of A/B/C final-temperature differences."""
    if len(curves) != 3:
        raise ValueError("Environment interpretation requires exactly three curves.")
    finals = [temperature_metrics_c(curve.result)["final_c"] for curve in curves]
    d_ba = finals[1] - finals[0]
    d_cb = finals[2] - finals[1]
    d_ca = finals[2] - finals[0]
    return (
        "Under the selected assumptions, including Earth infrared radiation "
        f"changes the final spacecraft temperature by {d_ba:+.2f} K. "
        f"Adding albedo produces a further change of {d_cb:+.2f} K "
        f"(C − A = {d_ca:+.2f} K). These are model results, not measured "
        "satellite temperatures."
    )


def default_inspect_curve_name(study: CompletedGuiStudy) -> str:
    """Default case used for 3D / heat-flow inspection after a solve."""
    if study.mode == "environment_compare":
        return study.primary.name  # Case C
    return study.primary.name


def resolve_inspect_curve(
    curves: tuple[NamedResult, ...],
    selected_name: str | None,
    default_name: str,
) -> NamedResult:
    """Pick an inspection curve without re-solving."""
    by_name = {curve.name: curve for curve in curves}
    if selected_name in by_name:
        return by_name[selected_name]
    if default_name in by_name:
        return by_name[default_name]
    return curves[-1]


def run_named_simulation(name: str, request: GuiRunRequest) -> NamedResult:
    """Solve one GUI request and package inputs with the result."""
    thermal, orbit, earth_ir, albedo = build_model_inputs(request)
    result = run_gui_simulation(request)
    return NamedResult(
        name=name,
        request=request,
        result=result,
        thermal=thermal,
        orbit=orbit,
        earth_infrared=earth_ir,
        albedo=albedo,
    )


def run_single_mode(request: GuiRunRequest) -> CompletedGuiStudy:
    """Mode 1: one user simulation."""
    primary = run_named_simulation(SINGLE_CASE_NAME, request)
    return CompletedGuiStudy(mode="single", primary=primary)


def run_baseline_comparison_mode(request: GuiRunRequest) -> CompletedGuiStudy:
    """Mode 2: default reference vs user-modified case."""
    baseline_request = default_gui_request()
    # Match orbit count and time step so the comparison is fair by default.
    baseline_request = GuiRunRequest(
        **{
            **baseline_request.__dict__,
            "orbit_count": request.orbit_count,
            "time_step_s": request.time_step_s,
        }
    )
    baseline = run_named_simulation(REF_CASE_NAME, baseline_request)
    modified = run_named_simulation(MOD_CASE_NAME, request)
    return CompletedGuiStudy(
        mode="baseline_compare",
        primary=modified,
        companions=(baseline,),
        changed_fields=changed_parameter_labels(baseline_request, request),
    )


def run_environment_comparison_mode(request: GuiRunRequest) -> CompletedGuiStudy:
    """Mode 3: No Earth heating → +Earth IR → +Earth IR + albedo."""
    case_a_req = GuiRunRequest(
        **{
            **request.__dict__,
            "include_earth_infrared": False,
            "include_albedo": False,
        }
    )
    case_b_req = GuiRunRequest(
        **{
            **request.__dict__,
            "include_earth_infrared": True,
            "include_albedo": False,
        }
    )
    case_c_req = GuiRunRequest(
        **{
            **request.__dict__,
            "include_earth_infrared": True,
            "include_albedo": True,
        }
    )
    case_a = run_named_simulation(ENV_CASE_A, case_a_req)
    case_b = run_named_simulation(ENV_CASE_B, case_b_req)
    case_c = run_named_simulation(ENV_CASE_C, case_c_req)
    return CompletedGuiStudy(
        mode="environment_compare",
        primary=case_c,
        companions=(case_a, case_b),
    )


def _pyplot():
    """Import pyplot with a headless-safe backend (Streamlit Community Cloud)."""
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    return plt


def _configure_plot_style(plt) -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 11,
            "axes.titlesize": 14,
            "axes.titleweight": "semibold",
            "axes.labelsize": 11,
            "axes.edgecolor": "#D2D2D7",
            "axes.labelcolor": "#1D1D1F",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": "#6E6E73",
            "ytick.color": "#6E6E73",
            "grid.color": "#E8E8ED",
            "grid.linewidth": 0.8,
            "legend.frameon": False,
            "figure.facecolor": "#FFFFFF",
            "axes.facecolor": "#FFFFFF",
            "text.color": "#1D1D1F",
        }
    )


def _shade_eclipses(axis, result: OrbitalThermalResult, label_once: list[bool]) -> None:
    intervals = eclipse_intervals_s(result.time_s, result.in_eclipse)
    for start_s, end_s in intervals:
        axis.axvspan(
            start_s / 60.0,
            end_s / 60.0,
            color="#D2D2D7",
            alpha=0.45,
            zorder=0,
            label="Eclipse" if label_once[0] else None,
        )
        label_once[0] = False


def make_gui_temperature_figure(
    result: OrbitalThermalResult,
    marker_index: int | None = None,
    title: str = "Orbital temperature",
    label: str = "Temperature",
):
    """Build a Matplotlib figure for Streamlit display."""
    from matplotlib.patches import Patch

    plt = _pyplot()
    _configure_plot_style(plt)
    time_min = [second / 60.0 for second in result.time_s]
    temp_c = [kelvin_to_celsius(temp_k) for temp_k in result.temperature_k]

    figure, axis = plt.subplots(figsize=(13.0, 5.8))
    _shade_eclipses(axis, result, [True])
    axis.plot(time_min, temp_c, color="#1D1D1F", linewidth=2.2, zorder=2, label=label)
    if marker_index is not None:
        marker_index = max(0, min(marker_index, len(result.time_s) - 1))
        axis.axvline(
            result.time_s[marker_index] / 60.0,
            color="#FF3B30",
            linewidth=1.2,
            linestyle="--",
            zorder=3,
            label="Selected time",
        )
        axis.scatter(
            [result.time_s[marker_index] / 60.0],
            [kelvin_to_celsius(result.temperature_k[marker_index])],
            color="#FF3B30",
            s=42,
            zorder=4,
            edgecolors="#FFFFFF",
            linewidths=1.0,
        )
    axis.set_xlabel("Time (minutes)")
    axis.set_ylabel("Temperature (°C)")
    axis.set_title(title, pad=12)
    axis.grid(True, axis="y", zorder=1)
    axis.grid(False, axis="x")
    handles = list(axis.lines) + [
        Patch(facecolor="#D2D2D7", edgecolor="none", alpha=0.9, label="Eclipse")
    ]
    axis.legend(handles=handles, loc="upper right", fontsize=10)
    axis.text(
        0.0,
        -0.18,
        "Single-node model · shaded bands mark eclipse.",
        transform=axis.transAxes,
        fontsize=9,
        color="#6E6E73",
    )
    figure.tight_layout()
    return figure


def make_comparison_temperature_figure(
    curves: tuple[NamedResult, ...],
    marker_index: int | None = None,
    marker_curve_name: str | None = None,
    title: str = "Temperature comparison",
    shade_from: NamedResult | None = None,
    emphasize_name: str | None = None,
):
    """Plot several histories. Eclipse shading uses shade_from (or first curve)."""
    from matplotlib.patches import Patch

    if not curves:
        raise ValueError("At least one curve is required.")
    plt = _pyplot()
    _configure_plot_style(plt)
    colors = ["#1D1D1F", "#0071E3", "#FF9500", "#5856D6"]
    styles = ["-", "--", "-.", ":"]
    figure, axis = plt.subplots(figsize=(13.0, 5.8))
    shade_source = shade_from or curves[0]
    different_orbits = any(
        abs(curve.orbit.altitude_m - shade_source.orbit.altitude_m) > 1.0
        for curve in curves
    )
    _shade_eclipses(axis, shade_source.result, [True])

    marker_curve = None
    emphasized = emphasize_name or marker_curve_name
    for index, curve in enumerate(curves):
        time_min = [second / 60.0 for second in curve.result.time_s]
        temp_c = [kelvin_to_celsius(temp_k) for temp_k in curve.result.temperature_k]
        is_focus = emphasized is not None and curve.name == emphasized
        axis.plot(
            time_min,
            temp_c,
            color=colors[index % len(colors)],
            linestyle=styles[index % len(styles)],
            linewidth=3.0 if is_focus else 1.7,
            alpha=1.0 if is_focus else 0.72,
            zorder=4 if is_focus else 2 + index,
            label=curve.name,
        )
        if marker_curve_name is not None and curve.name == marker_curve_name:
            marker_curve = curve
    if marker_curve is None:
        marker_curve = curves[-1]

    if marker_index is not None:
        marker_index = max(0, min(marker_index, len(marker_curve.result.time_s) - 1))
        axis.axvline(
            marker_curve.result.time_s[marker_index] / 60.0,
            color="#FF3B30",
            linewidth=1.2,
            linestyle="--",
            zorder=8,
            label="Selected time",
        )
        axis.scatter(
            [marker_curve.result.time_s[marker_index] / 60.0],
            [kelvin_to_celsius(marker_curve.result.temperature_k[marker_index])],
            color="#FF3B30",
            s=42,
            zorder=9,
            edgecolors="#FFFFFF",
            linewidths=1.0,
        )

    axis.set_xlabel("Time (minutes)")
    axis.set_ylabel("Temperature (°C)")
    axis.set_title(title, pad=12)
    axis.grid(True, axis="y", zorder=1)
    axis.grid(False, axis="x")
    note = (
        "Grey bands = eclipse (Earth blocks direct sunlight). "
        "Single-node model temperatures."
    )
    if different_orbits:
        note += (
            f" Eclipse shading follows '{shade_source.name}' only "
            "(orbit altitudes differ)."
        )
    axis.text(0.0, -0.18, note, transform=axis.transAxes, fontsize=9, color="#6E6E73")
    handles = list(axis.lines) + [
        Patch(
            facecolor="#D2D2D7",
            edgecolor="none",
            alpha=0.9,
            label=f"Eclipse ({shade_source.name})",
        )
    ]
    axis.legend(handles=handles, loc="best", fontsize=8, frameon=False)
    figure.tight_layout()
    return figure


def make_heat_flow_bar_figure(snapshot) -> object:
    """Horizontal bar chart of instantaneous heat flows."""
    plt = _pyplot()
    _configure_plot_style(plt)
    labels = [
        "Direct solar heating (+)",
        "Earth infrared heating (+)",
        "Albedo heating (+)",
        "Internal heating (+)",
        "Radiative cooling (−)",
        "Net thermal power",
    ]
    values = [
        snapshot.q_solar_w,
        snapshot.q_earth_ir_w,
        snapshot.q_albedo_w,
        snapshot.q_internal_w,
        -snapshot.q_radiated_w,
        snapshot.q_net_w,
    ]
    colors = ["#FFCC00", "#FF9500", "#34C759", "#8E8E93", "#FF3B30", "#0071E3"]
    figure, axis = plt.subplots(figsize=(13.0, 4.6))
    axis.barh(labels, values, color=colors, height=0.62, edgecolor="none")
    axis.axvline(0.0, color="#1D1D1F", linewidth=1.0)
    axis.set_xlabel("Power (W)  ·  positive heats · negative cools · net = inputs − radiated")
    axis.set_title("Heat flow at selected time", pad=12)
    axis.grid(True, axis="x", zorder=0)
    figure.tight_layout()
    return figure


def all_curves(study: CompletedGuiStudy) -> tuple[NamedResult, ...]:
    """Ordered curves for plotting a completed study."""
    if study.mode == "environment_compare":
        # companions are A, B; primary is C
        return (*study.companions, study.primary)
    if study.mode == "baseline_compare":
        return (*study.companions, study.primary)
    return (study.primary,)


def temperature_history_csv(curves: tuple[NamedResult, ...]) -> str:
    """CSV text for one or more temperature histories, including Q_internal(t)."""
    lines = [
        "case,time_s,time_min,temperature_c,in_eclipse,"
        "q_internal_w,internal_power_state"
    ]
    for curve in curves:
        schedule = power_schedule_from_request(curve.request)
        for time_s, temp_k, eclipsed in zip(
            curve.result.time_s,
            curve.result.temperature_k,
            curve.result.in_eclipse,
        ):
            q_internal = schedule.power_w_at(time_s, bool(eclipsed))
            state = schedule.state_label_at(time_s, bool(eclipsed))
            lines.append(
                f"{_csv_escape(curve.name)},"
                f"{time_s:.6f},"
                f"{time_s / 60.0:.6f},"
                f"{kelvin_to_celsius(temp_k):.6f},"
                f"{int(bool(eclipsed))},"
                f"{q_internal:.6f},"
                f"{_csv_escape(state)}"
            )
    return "\n".join(lines) + "\n"


def figure_to_png_bytes(figure) -> bytes:
    """Serialize a Matplotlib figure to PNG bytes for download (no disk writes)."""
    from io import BytesIO

    plt = _pyplot()
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    buffer.seek(0)
    png = buffer.getvalue()
    plt.close(figure)
    return png


def _csv_escape(value: str) -> str:
    if any(char in value for char in (",", '"', "\n")):
        return '"' + value.replace('"', '""') + '"'
    return value
