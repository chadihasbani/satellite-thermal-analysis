"""Circular low-Earth orbit and a cylindrical Earth-shadow test.

Coordinate frame
----------------
The origin is the center of a spherical Earth. Over one simulation the Sun
direction is fixed in this inertial frame. Orbital angle is measured in the
orbit plane from the point closest to the Sun, so angle 0 is the sun-facing
side (the satellite is above the subsolar point when beta is 0).

Beta angle
----------
Beta is the angle between the Sun vector and the orbital plane. The orbit
lies in the XY plane. The Sun unit vector is

    s = (cos(beta), 0, sin(beta))

The default reference case uses beta = 0 (Sun on +X, in the orbital plane).
The position at angle theta is

    r_vec = r * (cos(theta), sin(theta), 0)

Orbital period
--------------
    r = R_earth + altitude
    T_orbit = 2 * pi * sqrt(r**3 / mu)

Units are meters, seconds, and m^3/s^2.

Cylindrical shadow
-------------------
The Sun is treated as infinitely far away, so the umbra is a cylinder of
radius R_earth extending anti-sun from the terminator plane. A position is
in eclipse when both of these are true:

    r_vec · s < 0
    |r_vec × s| <= R_earth

The first condition places the satellite on the night side of the terminator
plane. The second places it inside the shadow cylinder. Atmospheric
refraction and the penumbra are not included. Eclipse length is the time this
test stays true. It is not a stored duration.

Critical beta and analytical eclipse duration
---------------------------------------------
With r_vec and s as above,

    |r_vec × s| = r * sqrt(sin^2(beta) + sin^2(theta) * cos^2(beta))

The night-side closest approach to the umbra axis is at theta = pi, where
that perpendicular distance is r |sin(beta)|. Eclipse is possible only when

    r |sin(beta)| <= R_earth
    |beta| <= beta_critical = asin(R_earth / r)

(Do not use acos(R_earth / r); that is the complementary angle 90° − beta_c.)

For |beta| < beta_critical and cos(beta) > 0, the night-side cylinder condition
requires |sin(theta)| <= kappa with

    kappa = sqrt( ((R_earth/r)^2 - sin^2(beta)) / cos^2(beta) )

so the continuous eclipse angle is 2 asin(kappa) and

    t_eclipse = (T_orbit / pi) * asin(kappa)

At |beta| = beta_critical the orbit is tangent to the cylinder at the
anti-sun point (measure-zero contact). This module reports analytical
duration 0 at and above critical beta. The discrete shadow test still
counts the tangent point because |r × s| <= R_earth includes equality.
Positive and negative beta give the same eclipse duration under this
cylindrical model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from satellite_thermal.validation import (
    require_finite_number,
    require_non_negative,
    require_positive,
)

ALTITUDE_M = 500_000.0
EARTH_RADIUS_M = 6_371_000.0
GRAVITATIONAL_PARAMETER_M3_PER_S2 = 3.986004418e14
BETA_RAD = 0.0


@dataclass(frozen=True)
class CircularOrbit:
    """Circular Earth orbit used by the Phase 2 sunlight/eclipse model.

    altitude_m:
        Height above the spherical Earth surface, in meters.
    earth_radius_m:
        Earth radius, in meters.
    gravitational_parameter_m3_per_s2:
        Earth gravitational parameter mu, in m^3/s^2.
    beta_rad:
        Angle between the Sun vector and the orbital plane, in radians.
        Default 0 preserves the Version 1.0 reference geometry.
    """

    altitude_m: float = ALTITUDE_M
    earth_radius_m: float = EARTH_RADIUS_M
    gravitational_parameter_m3_per_s2: float = GRAVITATIONAL_PARAMETER_M3_PER_S2
    beta_rad: float = BETA_RAD

    def validated(self) -> "CircularOrbit":
        """Return a copy with every field checked, or raise ValueError."""
        altitude = require_non_negative("altitude_m", self.altitude_m)
        earth_radius = require_positive("earth_radius_m", self.earth_radius_m)
        mu = require_positive(
            "gravitational_parameter_m3_per_s2",
            self.gravitational_parameter_m3_per_s2,
        )
        beta = require_finite_number("beta_rad", self.beta_rad)
        if abs(beta) > math.pi / 2.0:
            raise ValueError(
                f"beta_rad must be between -pi/2 and pi/2, got {beta}."
            )
        if altitude + earth_radius <= earth_radius:
            raise ValueError("orbital radius must be greater than the Earth radius.")
        return CircularOrbit(
            altitude_m=altitude,
            earth_radius_m=earth_radius,
            gravitational_parameter_m3_per_s2=mu,
            beta_rad=beta,
        )


def critical_beta_rad(orbit: CircularOrbit | None = None) -> float:
    """Largest |beta| with cylindrical-shadow eclipse possible: asin(R_earth / r).

    Derived from the night-side minimum |r × s| = r |sin(beta)| equaling
    R_earth at tangency. Returns radians in [0, pi/2).
    """
    settings = (orbit or CircularOrbit()).validated()
    radius = orbital_radius_m(settings)
    ratio = settings.earth_radius_m / radius
    if ratio > 1.0:
        raise ValueError("earth radius cannot exceed orbital radius.")
    return math.asin(ratio)


def analytical_eclipse_duration_s(orbit: CircularOrbit | None = None) -> float:
    """Closed-form cylindrical-umbra eclipse duration for one circular orbit.

    For |beta| < beta_critical:

        kappa = sqrt( ((R/r)^2 - sin^2(beta)) / cos^2(beta) )
        t_eclipse = (T_orbit / pi) * asin(kappa)

    For |beta| >= beta_critical the analytical duration is 0 (continuous
    sunlight, or measure-zero tangency at the critical boundary).
    """
    settings = (orbit or CircularOrbit()).validated()
    radius = orbital_radius_m(settings)
    ratio = settings.earth_radius_m / radius
    beta = settings.beta_rad
    sin_beta = math.sin(beta)
    if abs(sin_beta) >= ratio:
        return 0.0
    cos_beta = math.cos(beta)
    # |beta| <= pi/2 and below critical implies cos(beta) > 0 for circular LEO.
    kappa_sq = (ratio * ratio - sin_beta * sin_beta) / (cos_beta * cos_beta)
    if kappa_sq <= 0.0:
        return 0.0
    kappa = math.sqrt(min(1.0, kappa_sq))
    return (orbital_period_s(settings) / math.pi) * math.asin(kappa)


def orbital_radius_m(orbit: CircularOrbit | None = None) -> float:
    """Geocentric orbital radius r = R_earth + altitude, in meters."""
    settings = (orbit or CircularOrbit()).validated()
    return settings.earth_radius_m + settings.altitude_m


def orbital_period_s(orbit: CircularOrbit | None = None) -> float:
    """Circular orbital period T_orbit = 2*pi*sqrt(r**3/mu), in seconds."""
    settings = (orbit or CircularOrbit()).validated()
    radius = orbital_radius_m(settings)
    mu = settings.gravitational_parameter_m3_per_s2
    return 2.0 * math.pi * math.sqrt(radius**3 / mu)


def position_angle_rad(time_s: float, period_s: float) -> float:
    """Orbital angle from the sunward reference, in radians.

    The angle is 0 at the sun-facing side and increases by 2*pi each period.
    It is not wrapped, so several orbits keep a rising angle.
    """
    time = require_non_negative("time_s", time_s)
    period = require_positive("period_s", period_s)
    return 2.0 * math.pi * time / period


def sun_direction(beta_rad: float = BETA_RAD) -> tuple[float, float, float]:
    """Unit vector toward the Sun. beta = 0 returns +X."""
    beta = require_finite_number("beta_rad", beta_rad)
    return (math.cos(beta), 0.0, math.sin(beta))


def satellite_position_m(
    angle_rad: float,
    orbital_radius: float,
) -> tuple[float, float, float]:
    """Inertial satellite position in meters for an orbit in the XY plane."""
    angle = require_finite_number("angle_rad", angle_rad)
    radius = require_positive("orbital_radius_m", orbital_radius)
    return (
        radius * math.cos(angle),
        radius * math.sin(angle),
        0.0,
    )


def _unit_vector(name: str, vector: tuple[float, float, float]) -> tuple[float, float, float]:
    components = tuple(require_finite_number(f"{name}[{index}]", component) for index, component in enumerate(vector))
    magnitude = math.sqrt(sum(component * component for component in components))
    if magnitude == 0.0:
        raise ValueError(f"{name} must be a non-zero vector.")
    return tuple(component / magnitude for component in components)


def in_cylindrical_earth_shadow(
    position_m: tuple[float, float, float],
    earth_radius_m: float,
    sun_direction_vector: tuple[float, float, float] = (1.0, 0.0, 0.0),
) -> bool:
    """Return True when position_m lies in the cylindrical Earth umbra.

    r · s_hat < 0 and |r × s_hat| <= R_earth.
    """
    if len(position_m) != 3 or len(sun_direction_vector) != 3:
        raise ValueError("position and sun direction must be 3-vectors.")
    radius = require_positive("earth_radius_m", earth_radius_m)
    x, y, z = (
        require_finite_number("position_m[0]", position_m[0]),
        require_finite_number("position_m[1]", position_m[1]),
        require_finite_number("position_m[2]", position_m[2]),
    )
    sun_x, sun_y, sun_z = _unit_vector("sun_direction", sun_direction_vector)
    along_sun = x * sun_x + y * sun_y + z * sun_z
    cross_x = y * sun_z - z * sun_y
    cross_y = z * sun_x - x * sun_z
    cross_z = x * sun_y - y * sun_x
    perpendicular = math.sqrt(cross_x**2 + cross_y**2 + cross_z**2)
    return along_sun < 0.0 and perpendicular <= radius


def position_at_time_m(
    time_s: float,
    orbit: CircularOrbit | None = None,
) -> tuple[float, float, float]:
    """Satellite position at time_s, starting from the sunward side at t = 0."""
    settings = (orbit or CircularOrbit()).validated()
    angle = position_angle_rad(time_s, orbital_period_s(settings))
    return satellite_position_m(angle, orbital_radius_m(settings))


def in_eclipse_at_time(
    time_s: float,
    orbit: CircularOrbit | None = None,
) -> bool:
    """Earth-shadow test at time_s for this circular orbit."""
    settings = (orbit or CircularOrbit()).validated()
    return in_cylindrical_earth_shadow(
        position_at_time_m(time_s, settings),
        settings.earth_radius_m,
        sun_direction(settings.beta_rad),
    )


def eclipse_and_sunlight_durations_s(
    time_step_s: float,
    orbit: CircularOrbit | None = None,
) -> tuple[float, float]:
    """Eclipse and sunlight time over one orbit, in seconds.

    A step is eclipse when the shadow test is true at the beginning of that
    step. The two returned durations add up to one orbital period.
    """
    settings = (orbit or CircularOrbit()).validated()
    step_limit = require_positive("time_step_s", time_step_s)
    period = orbital_period_s(settings)
    elapsed = 0.0
    eclipse = 0.0
    sunlight = 0.0
    while elapsed < period:
        step = min(step_limit, period - elapsed)
        if in_eclipse_at_time(elapsed, settings):
            eclipse += step
        else:
            sunlight += step
        elapsed += step
    return eclipse, sunlight
