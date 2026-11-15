"""Prescribed spacecraft attitude (fixed inertial only).

Frames
------
Inertial (simulation): Earth-centred, orbit in the XY plane, Sun unit vector

    s = (cos(beta), 0, sin(beta))

pointing from the spacecraft toward the Sun (parallel-ray / distant-Sun
convention used by the cylindrical eclipse model).

Body axes
---------
This simplified simulator uses a single prescribed orientation:

``fixed_inertial`` — body +X,+Y,+Z stay aligned with inertial XYZ for the
whole run. Face-based (enhanced) solar heating uses those fixed axes.

Nadir-pointing and Sun-pointing modes are not offered in the simplified UI.
"""

from __future__ import annotations

import math
from enum import Enum

from satellite_thermal.validation import require_finite_number


class AttitudeMode(str, Enum):
    """Prescribed geometric attitudes available in enhanced mode."""

    FIXED_INERTIAL = "fixed_inertial"


def parse_attitude_mode(value: str | AttitudeMode) -> AttitudeMode:
    """Parse a GUI / request string into AttitudeMode."""
    if isinstance(value, AttitudeMode):
        return value
    normalized = str(value).strip().lower()
    if normalized != AttitudeMode.FIXED_INERTIAL.value:
        raise ValueError(
            "attitude_mode must be 'fixed_inertial' in this simplified simulator. "
            f"Got {value!r}."
        )
    return AttitudeMode.FIXED_INERTIAL


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
    singularity_cos_limit: float = 0.999999,
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]:
    """Body +X,+Y,+Z unit vectors expressed in the inertial frame."""
    del orbital_angle_rad, sun_direction_inertial, singularity_cos_limit
    parse_attitude_mode(attitude_mode)
    return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
