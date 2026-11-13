"""Simplified Earth-albedo (reflected sunlight) heating for Phase 3B.

Albedo is sunlight reflected by Earth. It is a solar-spectrum load, so it uses
the solar absorptivity alpha, not the infrared emissivity epsilon.

Governing expression
--------------------
    Q_albedo = alpha * A_albedo * F_albedo * a * S

where a is Earth's Bond albedo (dimensionless), S is the solar constant, and

    F_albedo = F_earth * max(cos(theta), 0)
    F_earth  = (R_earth / r_orbit)^2

theta is the orbital angle from the sunward / subsolar axis (theta = 0 at the
Phase 2 start). The cosine factor is a teaching approximation: reflected
sunlight is strongest over the day side and is forced to zero when the
satellite is over the night side of Earth.

Eclipse rule
------------
If the cylindrical shadow test says the satellite is in eclipse, Q_albedo = 0.
There is no reflected sunlight from a fully shadowed Earth disk in this model.

Assumptions
-----------
- a = 0.30 is a common global-mean Bond albedo used for teaching.
- A_albedo defaults to 0.01 m^2, matching the existing projected / Earth-facing
  area scale.
- Attitude is fixed; the factor does not include detailed BRDF or cloudy Earth.
- This is not a flight albedo model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from satellite_thermal.earth_infrared import earth_view_factor
from satellite_thermal.orbit import (
    CircularOrbit,
    in_eclipse_at_time,
    orbital_period_s,
    position_angle_rad,
)
from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.validation import (
    require_finite_number,
    require_fraction,
    require_non_negative,
    require_positive,
)

EARTH_BOND_ALBEDO = 0.30
DEFAULT_ALBEDO_AREA_M2 = 0.01


@dataclass(frozen=True)
class AlbedoParameters:
    """Inputs for the Phase 3B reflected-sunlight term.

    earth_bond_albedo:
        Fraction of sunlight reflected by Earth, a, dimensionless [0, 1].
    albedo_area_m2:
        Effective area intercepting reflected sunlight, A_albedo, in m^2.
    """

    earth_bond_albedo: float = EARTH_BOND_ALBEDO
    albedo_area_m2: float = DEFAULT_ALBEDO_AREA_M2

    def validated(self) -> "AlbedoParameters":
        """Return a copy with every field checked, or raise ValueError."""
        return AlbedoParameters(
            earth_bond_albedo=require_fraction(
                "earth_bond_albedo", self.earth_bond_albedo
            ),
            albedo_area_m2=require_positive("albedo_area_m2", self.albedo_area_m2),
        )


def albedo_geometry_factor(
    orbital_angle_rad: float,
    earth_view: float,
) -> float:
    """Sunlit-Earth geometric factor F_albedo = F_earth * max(cos(theta), 0)."""
    angle = require_finite_number("orbital_angle_rad", orbital_angle_rad)
    view = require_non_negative("earth_view", earth_view)
    if view > 1.0:
        raise ValueError(f"earth_view must be between 0 and 1, got {view}.")
    return view * max(math.cos(angle), 0.0)


def albedo_heating(
    solar_absorptivity: float,
    albedo_area_m2: float,
    earth_bond_albedo: float,
    solar_flux_w_per_m2: float,
    geometry_factor: float,
) -> float:
    """Absorbed albedo power in watts.

    Q_albedo = alpha * A_albedo * F_albedo * a * S
    """
    alpha = require_fraction("solar_absorptivity", solar_absorptivity)
    area = require_positive("albedo_area_m2", albedo_area_m2)
    bond = require_fraction("earth_bond_albedo", earth_bond_albedo)
    solar = require_non_negative("solar_flux_w_per_m2", solar_flux_w_per_m2)
    factor = require_non_negative("geometry_factor", geometry_factor)
    if factor > 1.0:
        raise ValueError(f"geometry_factor must be between 0 and 1, got {factor}.")
    return alpha * area * factor * bond * solar


def albedo_heat_w_at_time(
    time_s: float,
    orbit: CircularOrbit | None = None,
    thermal: Phase1Parameters | None = None,
    albedo: AlbedoParameters | None = None,
) -> float:
    """Absorbed albedo at time_s, in watts. Zero in eclipse."""
    orbit_settings = (orbit or CircularOrbit()).validated()
    thermal_settings = (thermal or Phase1Parameters()).validated()
    albedo_settings = (albedo or AlbedoParameters()).validated()

    if in_eclipse_at_time(time_s, orbit_settings):
        return 0.0

    period = orbital_period_s(orbit_settings)
    angle = position_angle_rad(time_s, period)
    factor = albedo_geometry_factor(angle, earth_view_factor(orbit_settings))
    return albedo_heating(
        solar_absorptivity=thermal_settings.absorptivity,
        albedo_area_m2=albedo_settings.albedo_area_m2,
        earth_bond_albedo=albedo_settings.earth_bond_albedo,
        solar_flux_w_per_m2=thermal_settings.solar_flux_w_per_m2,
        geometry_factor=factor,
    )
