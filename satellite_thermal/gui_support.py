"""Helpers for the Streamlit GUI.

These functions only assemble existing model inputs and plots. They do not
re-implement the thermal equations.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from satellite_thermal.albedo import AlbedoParameters
from satellite_thermal.earth_infrared import EarthInfraredParameters
from satellite_thermal.orbit import CircularOrbit, orbital_period_s
from satellite_thermal.orbital_simulation import (
    OrbitalThermalResult,
    eclipse_intervals_s,
    simulate_orbital_eclipse,
)
from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.units import kelvin_to_celsius
from satellite_thermal.validation import require_positive

# Soft cap so the GUI stays responsive for interactive runs.
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
    orbit_count: int
    time_step_s: float
    include_earth_infrared: bool
    include_albedo: bool


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
        orbit_count=5,
        time_step_s=5.0,
        include_earth_infrared=True,
        include_albedo=True,
    )


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
    orbit = CircularOrbit(altitude_m=request.altitude_km * 1000.0).validated()
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

    # Estimate sample count using the same orbit helper the solver uses.
    orbit = CircularOrbit(altitude_m=request.altitude_km * 1000.0).validated()
    duration_s = request.orbit_count * orbital_period_s(orbit)
    estimated_samples = int(duration_s / request.time_step_s) + 1
    if estimated_samples > MAX_GUI_SAMPLES:
        raise ValueError(
            "Requested run is too large for interactive use "
            f"(~{estimated_samples:,} samples; limit {MAX_GUI_SAMPLES:,}). "
            "Increase the time step or reduce the number of orbits."
        )
    return request


def request_fingerprint(mode: str, request: GuiRunRequest) -> tuple:
    """Hashable snapshot of the inputs that produced a displayed study."""
    return (mode, tuple(sorted(asdict(request).items())))


def run_gui_simulation(request: GuiRunRequest) -> OrbitalThermalResult:
    """Run the existing orbital solver from a GUI request."""
    validate_gui_request(request)
    thermal, orbit, earth_ir, albedo = build_model_inputs(request)
    return simulate_orbital_eclipse(
        orbit_count=request.orbit_count,
        time_step_s=request.time_step_s,
        parameters=thermal,
        orbit=orbit,
        include_earth_infrared=request.include_earth_infrared,
        earth_infrared=earth_ir,
        include_albedo=request.include_albedo,
        albedo=albedo,
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


_PARAMETER_LABELS = {
    "mass_kg": "mass",
    "specific_heat_j_per_kg_k": "cp",
    "initial_temperature_c": "initial T",
    "absorptivity": "alpha",
    "emissivity": "epsilon",
    "projected_area_m2": "A_projected",
    "radiating_area_m2": "A_radiating",
    "earth_facing_area_m2": "A_earth",
    "albedo_area_m2": "A_albedo",
    "internal_heat_w": "Q_internal",
    "solar_flux_w_per_m2": "S",
    "earth_olr_w_per_m2": "E_olr",
    "earth_bond_albedo": "Bond albedo",
    "altitude_km": "altitude",
    "orbit_count": "orbit count",
    "time_step_s": "time step",
    "include_earth_infrared": "Earth IR flag",
    "include_albedo": "albedo flag",
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
    """Rows for a baseline-vs-modified comparison table."""
    rows: list[dict[str, object]] = []
    for field, label in _PARAMETER_LABELS.items():
        base_value = getattr(baseline, field)
        mod_value = getattr(modified, field)
        if base_value != mod_value:
            rows.append(
                {
                    "Parameter": label,
                    "Baseline": base_value,
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
    primary = run_named_simulation("User simulation", request)
    return CompletedGuiStudy(mode="single", primary=primary)


def run_baseline_comparison_mode(request: GuiRunRequest) -> CompletedGuiStudy:
    """Mode 2: Phase 3B baseline vs user-modified case."""
    baseline_request = default_gui_request()
    # Match orbit count and time step so the comparison is fair by default.
    baseline_request = GuiRunRequest(
        **{
            **baseline_request.__dict__,
            "orbit_count": request.orbit_count,
            "time_step_s": request.time_step_s,
        }
    )
    baseline = run_named_simulation("Default reference case", baseline_request)
    modified = run_named_simulation("Modified", request)
    return CompletedGuiStudy(
        mode="baseline_compare",
        primary=modified,
        companions=(baseline,),
        changed_fields=changed_parameter_labels(baseline_request, request),
    )


def run_environment_comparison_mode(request: GuiRunRequest) -> CompletedGuiStudy:
    """Mode 3: solar-only, +Earth IR, +Earth IR + albedo."""
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
    case_a = run_named_simulation("A: solar + internal", case_a_req)
    case_b = run_named_simulation("B: + Earth IR", case_b_req)
    case_c = run_named_simulation("C: + Earth IR + albedo", case_c_req)
    return CompletedGuiStudy(
        mode="environment_compare",
        primary=case_c,
        companions=(case_a, case_b),
    )


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
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

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
):
    """Plot several histories. Eclipse shading uses shade_from (or first curve)."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    if not curves:
        raise ValueError("At least one curve is required.")
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
    for index, curve in enumerate(curves):
        time_min = [second / 60.0 for second in curve.result.time_s]
        temp_c = [kelvin_to_celsius(temp_k) for temp_k in curve.result.temperature_k]
        axis.plot(
            time_min,
            temp_c,
            color=colors[index % len(colors)],
            linestyle=styles[index % len(styles)],
            linewidth=2.2,
            zorder=2 + index,
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
    note = "Single-node model · shaded bands mark eclipse."
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
    axis.legend(handles=handles, loc="best", fontsize=9)
    figure.tight_layout()
    return figure


def make_heat_flow_bar_figure(snapshot) -> object:
    """Horizontal bar chart of instantaneous heat flows."""
    import matplotlib.pyplot as plt

    _configure_plot_style(plt)
    labels = [
        "Solar heating",
        "Earth IR heating",
        "Albedo heating",
        "Internal heat",
        "Radiative cooling",
        "Net heat flow",
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
    """CSV text for one or more temperature histories."""
    lines = ["case,time_s,time_min,temperature_c,in_eclipse"]
    for curve in curves:
        for time_s, temp_k, eclipsed in zip(
            curve.result.time_s,
            curve.result.temperature_k,
            curve.result.in_eclipse,
        ):
            lines.append(
                f"{_csv_escape(curve.name)},"
                f"{time_s:.6f},"
                f"{time_s / 60.0:.6f},"
                f"{kelvin_to_celsius(temp_k):.6f},"
                f"{int(bool(eclipsed))}"
            )
    return "\n".join(lines) + "\n"


def figure_to_png_bytes(figure) -> bytes:
    """Serialize a Matplotlib figure to PNG bytes for download."""
    from io import BytesIO

    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    buffer.seek(0)
    return buffer.getvalue()


def _csv_escape(value: str) -> str:
    if any(char in value for char in (",", '"', "\n")):
        return '"' + value.replace('"', '""') + '"'
    return value
