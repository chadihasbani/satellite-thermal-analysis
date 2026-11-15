"""Heat rates and the lumped energy balance for one satellite node.

Governing energy balance
------------------------
    m * cp * dT/dt = Q_solar + Q_internal + Q_earth_ir + Q_albedo - Q_radiated

Optional planetary loads default to zero so Phase 1 and Phase 2 results stay
unchanged. Phase 3A may enable Q_earth_ir. Phase 3B may also enable Q_albedo.

Solar heating
-------------
    Q_solar = alpha * A_projected * S
    Units: (dimensionless) * m^2 * (W / m^2) = W

Earth infrared heating (optional)
---------------------------------
    Q_earth_ir is an absorbed planetary IR load in watts. See earth_infrared.py.
    Default is 0 W.

Albedo heating (optional)
-------------------------
    Q_albedo is absorbed Earth-reflected sunlight in watts. See albedo.py.
    It uses solar absorptivity, not infrared emissivity. Default is 0 W.

Radiative cooling
-----------------
    Q_radiated = epsilon * sigma * A_radiating * T^4
    Units: (dimensionless) * (W / (m^2 K^4)) * m^2 * K^4 = W

Temperature derivative
----------------------
    dT/dt = (Q_solar + Q_internal + Q_earth_ir + Q_albedo - Q_radiated) / (m * cp)
    Units: W / (kg * J / (kg K)) = K / s
    because 1 W = 1 J / s.

Assumptions used by these functions
-----------------------------------
- The satellite is one isothermal node (lumped capacitance).
- Solar absorptivity and infrared emissivity are constant.
- Projected and radiating areas do not change with time.
- Q_radiated is emission from the node only toward a 0 K sink. Absorbed
  Earth infrared, when enabled, is added separately rather than as a
  coupled radiosity exchange with Earth.
- Q_internal is an imposed constant power, not a computed equipment model.
- These functions do not represent a flight thermal prediction.
"""

from __future__ import annotations

from satellite_thermal.parameters import STEFAN_BOLTZMANN
from satellite_thermal.validation import (
    require_finite_number,
    require_fraction,
    require_non_negative,
    require_positive,
)


def solar_heating(
    absorptivity: float,
    projected_area_m2: float,
    solar_flux_w_per_m2: float,
) -> float:
    """Absorbed solar power in watts.

    Q_solar = alpha * A_projected * S
    """
    alpha = require_fraction("absorptivity", absorptivity)
    area = require_positive("projected_area_m2", projected_area_m2)
    solar_flux = require_non_negative("solar_flux_w_per_m2", solar_flux_w_per_m2)
    return alpha * area * solar_flux


def radiative_cooling(
    emissivity: float,
    radiating_area_m2: float,
    temperature_k: float,
    stefan_boltzmann_w_per_m2_k4: float = STEFAN_BOLTZMANN,
) -> float:
    """Emitted thermal radiation in watts.

    Q_radiated = epsilon * sigma * A_radiating * T^4

    temperature_k must be an absolute temperature in kelvin.
    """
    epsilon = require_fraction("emissivity", emissivity)
    area = require_positive("radiating_area_m2", radiating_area_m2)
    temperature = require_positive("temperature_k", temperature_k)
    sigma = require_positive(
        "stefan_boltzmann_w_per_m2_k4", stefan_boltzmann_w_per_m2_k4
    )
    return epsilon * sigma * area * temperature**4


def temperature_derivative(
    temperature_k: float,
    mass_kg: float,
    specific_heat_j_per_kg_k: float,
    absorptivity: float,
    projected_area_m2: float,
    solar_flux_w_per_m2: float,
    internal_heat_w: float,
    emissivity: float,
    radiating_area_m2: float,
    stefan_boltzmann_w_per_m2_k4: float = STEFAN_BOLTZMANN,
    earth_infrared_heat_w: float = 0.0,
    albedo_heat_w: float = 0.0,
) -> float:
    """Node heating rate dT/dt in K/s.

    dT/dt = (Q_solar + Q_internal + Q_earth_ir + Q_albedo - Q_radiated) / (m * cp)

    Optional planetary loads default to 0 W so earlier phases keep their
    previous energy balance.
    """
    temperature = require_positive("temperature_k", temperature_k)
    mass = require_positive("mass_kg", mass_kg)
    specific_heat = require_positive(
        "specific_heat_j_per_kg_k", specific_heat_j_per_kg_k
    )
    internal_heat = require_finite_number("internal_heat_w", internal_heat_w)
    earth_ir = require_finite_number("earth_infrared_heat_w", earth_infrared_heat_w)
    albedo = require_finite_number("albedo_heat_w", albedo_heat_w)

    absorbed_solar = solar_heating(
        absorptivity, projected_area_m2, solar_flux_w_per_m2
    )
    emitted = radiative_cooling(
        emissivity,
        radiating_area_m2,
        temperature,
        stefan_boltzmann_w_per_m2_k4,
    )
    net_power_w = absorbed_solar + internal_heat + earth_ir + albedo - emitted
    thermal_capacity_j_per_k = mass * specific_heat
    return net_power_w / thermal_capacity_j_per_k


def energy_balance_rate(
    temperature_k: float,
    mass_kg: float,
    specific_heat_j_per_kg_k: float,
    q_solar_w: float,
    q_internal_w: float,
    q_radiated_w: float,
    q_earth_ir_w: float = 0.0,
    q_albedo_w: float = 0.0,
) -> float:
    """dT/dt from precomputed heat loads, in K/s.

    Used by the enhanced face-based solar / radiation path so the integrator
    and GUI heat-flow panel share the same watt-level terms.
    """
    require_positive("temperature_k", temperature_k)
    mass = require_positive("mass_kg", mass_kg)
    specific_heat = require_positive(
        "specific_heat_j_per_kg_k", specific_heat_j_per_kg_k
    )
    q_solar = require_finite_number("q_solar_w", q_solar_w)
    q_internal = require_finite_number("q_internal_w", q_internal_w)
    q_radiated = require_finite_number("q_radiated_w", q_radiated_w)
    q_earth_ir = require_finite_number("q_earth_ir_w", q_earth_ir_w)
    q_albedo = require_finite_number("q_albedo_w", q_albedo_w)
    return (
        q_solar + q_internal + q_earth_ir + q_albedo - q_radiated
    ) / (mass * specific_heat)
