"""Prescribed spacecraft attitude modes (geometry only; not closed-loop ACS).

Frames
------
Inertial (simulation): Earth-centred, orbit in the XY plane, Sun unit vector

    s = (cos(beta), 0, sin(beta))

pointing from the spacecraft toward the Sun (parallel-ray / distant-Sun
convention used by the cylindrical eclipse model).

Orbital / LVLH basis at orbital angle theta (from the sunward reference):

    r_hat     = (cos theta, sin theta, 0)     # geocentric radial, outward
    theta_hat = (-sin theta, cos theta, 0)    # along-track
    h_hat     = (0, 0, 1)                     # orbit normal

Right-handed: r_hat × theta_hat = h_hat.

Body axes
---------
Body +X, +Y, +Z form a right-handed triad. Attitude modes prescribe how those
axes are expressed in the inertial frame.

1. fixed_inertial
   Body axes stay aligned with inertial XYZ for the whole run.
   Singularities: none.

2. nadir_pointing
   Body +Z toward nadir (-r_hat), body +X along-track (theta_hat),
   body +Y = +Z × +X = -h_hat for this circular equatorial orbit.
   Singularities: none for a circular orbit with well-defined r_hat.

3. sun_pointing
   Body +X toward the Sun (s). Roll about +X is fixed by preferring the
   orbit-normal reference h_hat to build +Y = normalize(h_hat × +X).
   If |s · h_hat| is within ``singularity_cos_limit`` of 1 (Sun nearly along
   ± orbit normal), the secondary reference switches to theta_hat so that
   +Y = normalize(theta_hat × +X). If that cross product is still too small,
   inertial +Y is used as a final fallback.
"""

from __future__ import annotations

import math
from enum import Enum

from satellite_thermal.validation import require_finite_number

# If |dot(primary, reference)| exceeds this, the reference is nearly parallel
# to the primary axis and a different secondary reference is used.
DEFAULT_SINGULARITY_COS_LIMIT = 0.999999  # about 0.08 deg of alignment


class AttitudeMode(str, Enum):
    """Prescribed geometric attitudes available in enhanced mode."""

    FIXED_INERTIAL = "fixed_inertial"
    NADIR_POINTING = "nadir_pointing"
    SUN_POINTING = "sun_pointing"


def parse_attitude_mode(value: str | AttitudeMode) -> AttitudeMode:
    """Parse a GUI / request string into AttitudeMode."""
    if isinstance(value, AttitudeMode):
        return value
    try:
        return AttitudeMode(str(value).strip().lower())
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in AttitudeMode)
        raise ValueError(
            f"attitude_mode must be one of: {allowed}. Got {value!r}."
        ) from exc


def _unit(name: str, vector: tuple[float, float, float]) -> tuple[float, float, float]:
    x = require_finite_number(f"{name}[0]", vector[0])
    y = require_finite_number(f"{name}[1]", vector[1])
    z = require_finite_number(f"{name}[2]", vector[2])
    magnitude = math.sqrt(x * x + y * y + z * z)
    if magnitude == 0.0:
        raise ValueError(f"{name} must be a non-zero vector.")
    return (x / magnitude, y / magnitude, z / magnitude)


def _cross(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def orbital_basis(
    orbital_angle_rad: float,
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]:
    """Return (r_hat, theta_hat, h_hat) for the circular XY orbit."""
    theta = require_finite_number("orbital_angle_rad", orbital_angle_rad)
    r_hat = (math.cos(theta), math.sin(theta), 0.0)
    theta_hat = (-math.sin(theta), math.cos(theta), 0.0)
    h_hat = (0.0, 0.0, 1.0)
    return r_hat, theta_hat, h_hat


def body_axes_inertial(
    attitude_mode: str | AttitudeMode,
    orbital_angle_rad: float,
    sun_direction_inertial: tuple[float, float, float],
    singularity_cos_limit: float = DEFAULT_SINGULARITY_COS_LIMIT,
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]:
    """Body +X,+Y,+Z unit vectors expressed in the inertial frame."""
    mode = parse_attitude_mode(attitude_mode)
    limit = require_finite_number("singularity_cos_limit", singularity_cos_limit)
    if not 0.0 < limit <= 1.0:
        raise ValueError("singularity_cos_limit must be in (0, 1].")

    if mode is AttitudeMode.FIXED_INERTIAL:
        return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)

    r_hat, theta_hat, h_hat = orbital_basis(orbital_angle_rad)

    if mode is AttitudeMode.NADIR_POINTING:
        body_z = (-r_hat[0], -r_hat[1], -r_hat[2])  # nadir
        body_x = theta_hat  # along-track
        body_y = _unit("body_y", _cross(body_z, body_x))
        # Re-orthogonalize +X against the completed triad for numerical safety.
        body_x = _unit("body_x", _cross(body_y, body_z))
        return body_x, body_y, body_z

    # SUN_POINTING
    body_x = _unit("sun_direction", sun_direction_inertial)
    # Prefer orbit-normal secondary reference; fall back near singularity.
    if abs(_dot(body_x, h_hat)) < limit:
        secondary = h_hat
    elif abs(_dot(body_x, theta_hat)) < limit:
        secondary = theta_hat
    else:
        secondary = (0.0, 1.0, 0.0)
    y_raw = _cross(secondary, body_x)
    if math.sqrt(_dot(y_raw, y_raw)) < 1.0e-12:
        # Final fallback: any axis not parallel to body_x.
        secondary = (0.0, 0.0, 1.0) if abs(body_x[2]) < limit else (0.0, 1.0, 0.0)
        y_raw = _cross(secondary, body_x)
    body_y = _unit("body_y", y_raw)
    body_z = _unit("body_z", _cross(body_x, body_y))
    return body_x, body_y, body_z
