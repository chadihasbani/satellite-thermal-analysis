"""Orbital thermal march: energy balance plus geometric eclipse.

Legacy mode
-----------
Direct solar heating uses the fixed projected-area Phase 1 term while the
satellite is in sunlight and is zero in eclipse. Radiative emission uses the
fixed radiating area.

Enhanced mode
-------------
Solar absorption sums face contributions
``alpha_i * S * A_i * max(0, n_i · s)`` with prescribed attitude. Emission
sums ``epsilon_i * sigma * A_i * T^4`` over the six bus faces. Earth IR and
albedo remain the Version 1.0 effective-area loads (documented limitation).

The integrator is explicit Euler:

    T_new = T + dt * dT/dt(... at the start of the step)

The run starts at the sunward position and covers an integer number of orbits.
"""

from __future__ import annotations

from dataclasses import dataclass

from satellite_thermal.albedo import AlbedoParameters, albedo_heat_w_at_time
from satellite_thermal.attitude import AttitudeMode, body_axes_inertial, parse_attitude_mode
from satellite_thermal.earth_infrared import EarthInfraredParameters, earth_infrared_heat_w
from satellite_thermal.heat_transfer import energy_balance_rate, temperature_derivative
from satellite_thermal.orbit import (
    CircularOrbit,
    eclipse_and_sunlight_durations_s,
    in_eclipse_at_time,
    orbital_period_s,
    position_angle_rad,
    sun_direction,
)
from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.spacecraft_geometry import RectangularBusGeometry
from satellite_thermal.surface_heating import (
    surface_radiative_cooling_w,
    surface_solar_heating_w,
)
from satellite_thermal.validation import require_positive

THERMAL_MODEL_LEGACY = "legacy"
THERMAL_MODEL_ENHANCED = "enhanced"


def parse_thermal_model(value: str) -> str:
    """Return 'legacy' or 'enhanced'."""
    normalized = str(value).strip().lower()
    if normalized not in (THERMAL_MODEL_LEGACY, THERMAL_MODEL_ENHANCED):
        raise ValueError(
            "thermal_model must be 'legacy' or 'enhanced', "
            f"got {value!r}."
        )
    return normalized


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
    or 0.0 when Earth IR is off. include_albedo records whether the
    angle-dependent albedo term was enabled.
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
    include_albedo: bool = False

    def __post_init__(self) -> None:
        if not (len(self.time_s) == len(self.temperature_k) == len(self.in_eclipse)):
            raise ValueError("time, temperature, and eclipse flags must have the same length.")
        if len(self.time_s) == 0:
            raise ValueError("OrbitalThermalResult must contain at least one sample.")


def _enhanced_solar_and_radiated_w(
    time_s: float,
    temperature_k: float,
    thermal: Phase1Parameters,
    orbit: CircularOrbit,
    geometry: RectangularBusGeometry,
    attitude_mode: AttitudeMode,
) -> tuple[float, float]:
    """Face-based Q_solar and Q_radiated at one instant."""
    flux = solar_flux_w_per_m2(time_s, orbit, thermal)
    sun = sun_direction(orbit.beta_rad)
    angle = position_angle_rad(time_s, orbital_period_s(orbit))
    body_x, body_y, body_z = body_axes_inertial(attitude_mode, angle, sun)
    q_solar = surface_solar_heating_w(
        geometry, body_x, body_y, body_z, sun, flux
    )
    q_radiated = surface_radiative_cooling_w(
        geometry,
        temperature_k,
        thermal.stefan_boltzmann_w_per_m2_k4,
    )
    return q_solar, q_radiated


def simulate_orbital_eclipse(
    orbit_count: int = 5,
    time_step_s: float = 1.0,
    parameters: Phase1Parameters | None = None,
    orbit: CircularOrbit | None = None,
    include_earth_infrared: bool = False,
    earth_infrared: EarthInfraredParameters | None = None,
    include_albedo: bool = False,
    albedo: AlbedoParameters | None = None,
    thermal_model: str = THERMAL_MODEL_LEGACY,
    geometry: RectangularBusGeometry | None = None,
    attitude_mode: str | AttitudeMode = AttitudeMode.FIXED_INERTIAL,
) -> OrbitalThermalResult:
    """Integrate the single-node balance over complete circular orbits.

    Default thermal_model='legacy' preserves Version 1.0 fixed-area behaviour.
    Enhanced mode uses rectangular-bus face solar absorption and face-sum
    emission; Earth IR / albedo stay effective-area loads.
    """
    if isinstance(orbit_count, bool) or not isinstance(orbit_count, int) or orbit_count <= 0:
        raise ValueError(f"orbit_count must be a positive integer, got {orbit_count!r}.")
    if not isinstance(include_earth_infrared, bool):
        raise ValueError(
            f"include_earth_infrared must be a bool, got {include_earth_infrared!r}."
        )
    if not isinstance(include_albedo, bool):
        raise ValueError(f"include_albedo must be a bool, got {include_albedo!r}.")
    model = parse_thermal_model(thermal_model)
    step_limit = require_positive("time_step_s", time_step_s)
    thermal = (parameters or Phase1Parameters()).validated()
    orbit_settings = (orbit or CircularOrbit()).validated()
    albedo_settings = (albedo or AlbedoParameters()).validated() if include_albedo else None
    attitude = parse_attitude_mode(attitude_mode)
    bus = (
        (geometry or RectangularBusGeometry()).validated()
        if model == THERMAL_MODEL_ENHANCED
        else None
    )
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
        albedo_w = (
            albedo_heat_w_at_time(elapsed, orbit_settings, thermal, albedo_settings)
            if include_albedo
            else 0.0
        )
        if model == THERMAL_MODEL_ENHANCED:
            assert bus is not None
            q_solar, q_radiated = _enhanced_solar_and_radiated_w(
                elapsed,
                temperature_k[-1],
                thermal,
                orbit_settings,
                bus,
                attitude,
            )
            rate = energy_balance_rate(
                temperature_k=temperature_k[-1],
                mass_kg=thermal.mass_kg,
                specific_heat_j_per_kg_k=thermal.specific_heat_j_per_kg_k,
                q_solar_w=q_solar,
                q_internal_w=thermal.internal_heat_w,
                q_radiated_w=q_radiated,
                q_earth_ir_w=earth_ir_w,
                q_albedo_w=albedo_w,
            )
        else:
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
                albedo_heat_w=albedo_w,
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
        include_albedo=include_albedo,
    )
