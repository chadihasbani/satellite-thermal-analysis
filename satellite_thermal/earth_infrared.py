"""Simplified absorbed Earth infrared heating (Phase 3A).

Outgoing terrestrial infrared
-----------------------------
E_olr is an illustrative global-mean outgoing longwave radiation near the top
of Earth's atmosphere, in W/m^2. It is a property of the Earth/atmosphere
system. It is not the irradiance on the spacecraft until geometry converts
it through a view factor and an Earth-facing area.

Absorbed heating
----------------
    Q_earth_ir = alpha_ir * A_earth * F_earth * E_olr

with the nadir-facing flat-plate view factor to a spherical Earth

    F_earth = (R_earth / r_orbit)^2
    r_orbit = R_earth + altitude

Units: (dimensionless) * m^2 * (dimensionless) * (W/m^2) = W.

Infrared absorptivity
---------------------
For a gray surface Kirchhoff's law gives alpha_ir = epsilon. Phase 3A
defaults alpha_ir to the existing infrared emissivity 0.80.

Relation to radiation-to-space
-----------------------------
Phase 1 and Phase 2 still use

    Q_radiated = epsilon * sigma * A_radiating * T**4

as emission toward a 0 K sink. Phase 3A adds Q_earth_ir as a separate
absorbed load. That is a teaching decomposition, not an exact enclosure
exchange between the spacecraft and Earth. Surfaces that see Earth are not
re-assigned a reduced space view factor, and Earth is not treated as a
radiating blackbody at an Earth temperature in the energy balance.

Assumptions
-----------
- Circular 500 km orbit: F_earth is constant.
- A_earth is a constant effective Earth-facing area (default 0.01 m^2).
- E_olr is uniform and constant. Day/night Earth IR variation is ignored.
- Available in sunlight and in eclipse.
- Albedo is not included.
"""

from __future__ import annotations

from dataclasses import dataclass

from satellite_thermal.orbit import CircularOrbit, orbital_radius_m
from satellite_thermal.validation import (
    require_fraction,
    require_non_negative,
    require_positive,
)

# Illustrative global-mean OLR near the top of the atmosphere, W/m^2.
# Typical textbook / CERES-order value used for teaching, not a local
# orbital measurement.
EARTH_OLR_W_PER_M2 = 240.0

# Effective nadir-facing area for the lumped node, m^2. Chosen to match the
# existing projected-area scale (one face of a ~0.1 m class body).
DEFAULT_EARTH_FACING_AREA_M2 = 0.01

# Gray-body IR absorptivity default: equal to the Phase 1 emissivity.
DEFAULT_INFRARED_ABSORPTIVITY = 0.80


@dataclass(frozen=True)
class EarthInfraredParameters:
    """Inputs for the Phase 3A Earth-infrared heating term.

    earth_olr_w_per_m2:
        Illustrative TOA outgoing longwave radiation, E_olr, in W/m^2.
    earth_facing_area_m2:
        Effective spacecraft area that intercepts Earth IR, A_earth, in m^2.
    infrared_absorptivity:
        IR absorptivity, alpha_ir, dimensionless, from 0 to 1.
        Default equals the Phase 1 emissivity under Kirchhoff's law.
    """

    earth_olr_w_per_m2: float = EARTH_OLR_W_PER_M2
    earth_facing_area_m2: float = DEFAULT_EARTH_FACING_AREA_M2
    infrared_absorptivity: float = DEFAULT_INFRARED_ABSORPTIVITY

    def validated(self) -> "EarthInfraredParameters":
        """Return a copy with every field checked, or raise ValueError."""
        return EarthInfraredParameters(
            earth_olr_w_per_m2=require_non_negative(
                "earth_olr_w_per_m2", self.earth_olr_w_per_m2
            ),
            earth_facing_area_m2=require_positive(
                "earth_facing_area_m2", self.earth_facing_area_m2
            ),
            infrared_absorptivity=require_fraction(
                "infrared_absorptivity", self.infrared_absorptivity
            ),
        )


def earth_view_factor(orbit: CircularOrbit | None = None) -> float:
    """Nadir-facing flat-plate view factor to a spherical Earth.

    F_earth = (R_earth / r_orbit)^2
    """
    settings = (orbit or CircularOrbit()).validated()
    radius_orbit = orbital_radius_m(settings)
    return (settings.earth_radius_m / radius_orbit) ** 2


def earth_infrared_heating(
    infrared_absorptivity: float,
    earth_facing_area_m2: float,
    earth_olr_w_per_m2: float,
    view_factor: float,
) -> float:
    """Absorbed Earth infrared power in watts.

    Q_earth_ir = alpha_ir * A_earth * F_earth * E_olr
    """
    alpha_ir = require_fraction("infrared_absorptivity", infrared_absorptivity)
    area = require_positive("earth_facing_area_m2", earth_facing_area_m2)
    olr = require_non_negative("earth_olr_w_per_m2", earth_olr_w_per_m2)
    factor = require_non_negative("view_factor", view_factor)
    if factor > 1.0:
        raise ValueError(f"view_factor must be between 0 and 1, got {factor}.")
    return alpha_ir * area * factor * olr


def earth_infrared_heat_w(
    orbit: CircularOrbit | None = None,
    parameters: EarthInfraredParameters | None = None,
) -> float:
    """Absorbed Earth IR for this circular orbit, in watts."""
    settings = (parameters or EarthInfraredParameters()).validated()
    return earth_infrared_heating(
        infrared_absorptivity=settings.infrared_absorptivity,
        earth_facing_area_m2=settings.earth_facing_area_m2,
        earth_olr_w_per_m2=settings.earth_olr_w_per_m2,
        view_factor=earth_view_factor(orbit),
    )
