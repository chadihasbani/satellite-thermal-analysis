"""Heat rates and the lumped energy balance for one satellite node.

Governing energy balance
------------------------
    m * cp * dT/dt = Q_solar + Q_internal - Q_radiated

Solar heating
-------------
    Q_solar = alpha * A_projected * S
    Units: (dimensionless) * m^2 * (W / m^2) = W

Radiative cooling
-----------------
    Q_radiated = epsilon * sigma * A_radiating * T^4
    Units: (dimensionless) * (W / (m^2 K^4)) * m^2 * K^4 = W

Temperature derivative
----------------------
    dT/dt = (Q_solar + Q_internal - Q_radiated) / (m * cp)
    Units: W / (kg * J / (kg K)) = K / s
    because 1 W = 1 J / s.

Assumptions used by these functions
-----------------------------------
- The satellite is one isothermal node (lumped capacitance).
- Solar absorptivity and infrared emissivity are constant.
- Projected and radiating areas do not change with time.
- Q_radiated is emission from the node only. The supplied equation has no
  absorbed Earth-infrared term and no environment temperature, so this term
  corresponds to emission toward a 0 K sink.
- Q_internal is an imposed constant power, not a computed equipment model.
- These functions do not represent orbital geometry, eclipse, or a flight
  thermal prediction.
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
) -> float:
    """Node heating rate dT/dt in K/s.

    dT/dt = (Q_solar + Q_internal - Q_radiated) / (m * cp)
    """
    temperature = require_positive("temperature_k", temperature_k)
    mass = require_positive("mass_kg", mass_kg)
    specific_heat = require_positive(
        "specific_heat_j_per_kg_k", specific_heat_j_per_kg_k
    )
    internal_heat = require_finite_number("internal_heat_w", internal_heat_w)

    absorbed_solar = solar_heating(
        absorptivity, projected_area_m2, solar_flux_w_per_m2
    )
    emitted = radiative_cooling(
        emissivity,
        radiating_area_m2,
        temperature,
        stefan_boltzmann_w_per_m2_k4,
    )
    net_power_w = absorbed_solar + internal_heat - emitted
    thermal_capacity_j_per_k = mass * specific_heat
    return net_power_w / thermal_capacity_j_per_k
