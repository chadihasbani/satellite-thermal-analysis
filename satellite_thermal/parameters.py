"""Default Phase 1 parameters and their units.

All temperatures passed through this model stay in kelvin until a display
helper converts them.
"""

from __future__ import annotations

from dataclasses import dataclass

from satellite_thermal.validation import (
    require_finite_number,
    require_fraction,
    require_non_negative,
    require_positive,
)

# Stefan-Boltzmann constant, W / (m^2 K^4).
STEFAN_BOLTZMANN = 5.670374419e-8


@dataclass(frozen=True)
class Phase1Parameters:
    """Lumped thermal properties for one satellite node in sunlight.

    Attributes
    ----------
    mass_kg:
        Node mass, m, in kg.
    specific_heat_j_per_kg_k:
        Specific heat, cp, in J / (kg K).
    initial_temperature_k:
        Initial node temperature in K.
    solar_flux_w_per_m2:
        Incident solar flux, S, in W / m^2.
    absorptivity:
        Solar absorptivity, alpha, dimensionless, from 0 to 1.
    emissivity:
        Infrared emissivity, epsilon, dimensionless, from 0 to 1.
    projected_area_m2:
        Area intercepting sunlight, A_projected, in m^2.
    radiating_area_m2:
        Area emitting thermal radiation, A_radiating, in m^2.
    internal_heat_w:
        Constant internal dissipation, Q_internal, in W.
    stefan_boltzmann_w_per_m2_k4:
        Stefan-Boltzmann constant, sigma, in W / (m^2 K^4).
    """

    mass_kg: float = 5.0
    specific_heat_j_per_kg_k: float = 900.0
    initial_temperature_k: float = 293.15
    solar_flux_w_per_m2: float = 1361.0
    absorptivity: float = 0.60
    emissivity: float = 0.80
    projected_area_m2: float = 0.01
    radiating_area_m2: float = 0.06
    internal_heat_w: float = 5.0
    stefan_boltzmann_w_per_m2_k4: float = STEFAN_BOLTZMANN

    def validated(self) -> "Phase1Parameters":
        """Return a copy with every field checked, or raise ValueError."""
        return Phase1Parameters(
            mass_kg=require_positive("mass_kg", self.mass_kg),
            specific_heat_j_per_kg_k=require_positive(
                "specific_heat_j_per_kg_k", self.specific_heat_j_per_kg_k
            ),
            initial_temperature_k=require_positive(
                "initial_temperature_k", self.initial_temperature_k
            ),
            solar_flux_w_per_m2=require_non_negative(
                "solar_flux_w_per_m2", self.solar_flux_w_per_m2
            ),
            absorptivity=require_fraction("absorptivity", self.absorptivity),
            emissivity=require_fraction("emissivity", self.emissivity),
            projected_area_m2=require_positive(
                "projected_area_m2", self.projected_area_m2
            ),
            radiating_area_m2=require_positive(
                "radiating_area_m2", self.radiating_area_m2
            ),
            internal_heat_w=require_finite_number(
                "internal_heat_w", self.internal_heat_w
            ),
            stefan_boltzmann_w_per_m2_k4=require_positive(
                "stefan_boltzmann_w_per_m2_k4", self.stefan_boltzmann_w_per_m2_k4
            ),
        )
