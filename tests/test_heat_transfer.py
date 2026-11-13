"""Unit tests for Phase 1 heat rates, energy balance, and input checks."""

from __future__ import annotations

import math
import unittest

from satellite_thermal.heat_transfer import (
    radiative_cooling,
    solar_heating,
    temperature_derivative,
)
from satellite_thermal.parameters import STEFAN_BOLTZMANN, Phase1Parameters
from satellite_thermal.simulation import simulate_continuous_sunlight
from satellite_thermal.units import kelvin_to_celsius


class SolarHeatingTests(unittest.TestCase):
    def test_default_parameters_match_the_specified_product(self) -> None:
        heating_w = solar_heating(
            absorptivity=0.60,
            projected_area_m2=0.01,
            solar_flux_w_per_m2=1361.0,
        )
        self.assertTrue(math.isclose(heating_w, 8.166, rel_tol=0.0, abs_tol=1e-12))

    def test_zero_solar_flux_absorbs_nothing(self) -> None:
        self.assertEqual(
            solar_heating(0.60, 0.01, 0.0),
            0.0,
        )


class RadiativeCoolingTests(unittest.TestCase):
    def test_matches_stefan_boltzmann_expression(self) -> None:
        emissivity = 0.80
        area_m2 = 0.06
        temperature_k = 293.15
        expected_w = emissivity * STEFAN_BOLTZMANN * area_m2 * temperature_k**4
        actual_w = radiative_cooling(emissivity, area_m2, temperature_k)
        self.assertTrue(math.isclose(actual_w, expected_w, rel_tol=1e-12, abs_tol=0.0))

    def test_doubling_emissivity_doubles_emission(self) -> None:
        base = radiative_cooling(0.40, 0.06, 300.0)
        doubled = radiative_cooling(0.80, 0.06, 300.0)
        self.assertTrue(math.isclose(doubled, 2.0 * base, rel_tol=1e-12, abs_tol=0.0))


class TemperatureBalanceTests(unittest.TestCase):
    def test_derivative_uses_net_power_over_thermal_capacity(self) -> None:
        settings = Phase1Parameters()
        temperature_k = settings.initial_temperature_k
        solar_w = solar_heating(
            settings.absorptivity,
            settings.projected_area_m2,
            settings.solar_flux_w_per_m2,
        )
        radiated_w = radiative_cooling(
            settings.emissivity,
            settings.radiating_area_m2,
            temperature_k,
            settings.stefan_boltzmann_w_per_m2_k4,
        )
        expected_k_per_s = (
            solar_w + settings.internal_heat_w - radiated_w
        ) / (settings.mass_kg * settings.specific_heat_j_per_kg_k)

        actual_k_per_s = temperature_derivative(
            temperature_k=temperature_k,
            mass_kg=settings.mass_kg,
            specific_heat_j_per_kg_k=settings.specific_heat_j_per_kg_k,
            absorptivity=settings.absorptivity,
            projected_area_m2=settings.projected_area_m2,
            solar_flux_w_per_m2=settings.solar_flux_w_per_m2,
            internal_heat_w=settings.internal_heat_w,
            emissivity=settings.emissivity,
            radiating_area_m2=settings.radiating_area_m2,
        )
        self.assertTrue(
            math.isclose(actual_k_per_s, expected_k_per_s, rel_tol=1e-12, abs_tol=0.0)
        )

    def test_explicit_euler_advances_one_step_from_the_initial_rate(self) -> None:
        settings = Phase1Parameters()
        step_s = 1.0
        initial_rate = temperature_derivative(
            temperature_k=settings.initial_temperature_k,
            mass_kg=settings.mass_kg,
            specific_heat_j_per_kg_k=settings.specific_heat_j_per_kg_k,
            absorptivity=settings.absorptivity,
            projected_area_m2=settings.projected_area_m2,
            solar_flux_w_per_m2=settings.solar_flux_w_per_m2,
            internal_heat_w=settings.internal_heat_w,
            emissivity=settings.emissivity,
            radiating_area_m2=settings.radiating_area_m2,
        )
        result = simulate_continuous_sunlight(
            duration_s=step_s,
            time_step_s=step_s,
            parameters=settings,
        )
        self.assertEqual(result.time_s, (0.0, 1.0))
        self.assertTrue(
            math.isclose(
                result.temperature_k[1],
                settings.initial_temperature_k + step_s * initial_rate,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        )

    def test_default_case_cools_because_emission_exceeds_heat_input(self) -> None:
        result = simulate_continuous_sunlight(
            duration_s=60.0,
            time_step_s=1.0,
            parameters=Phase1Parameters(),
        )
        self.assertGreater(result.temperature_k[0], result.temperature_k[-1])
        self.assertTrue(
            math.isclose(kelvin_to_celsius(293.15), 20.0, rel_tol=0.0, abs_tol=1e-12)
        )


class InvalidInputTests(unittest.TestCase):
    def test_solar_heating_rejects_absorptivity_above_one(self) -> None:
        with self.assertRaises(ValueError):
            solar_heating(1.2, 0.01, 1361.0)

    def test_solar_heating_rejects_negative_area(self) -> None:
        with self.assertRaises(ValueError):
            solar_heating(0.60, -0.01, 1361.0)

    def test_radiative_cooling_rejects_non_positive_temperature(self) -> None:
        with self.assertRaises(ValueError):
            radiative_cooling(0.80, 0.06, 0.0)
        with self.assertRaises(ValueError):
            radiative_cooling(0.80, 0.06, -10.0)

    def test_temperature_derivative_rejects_non_positive_mass_and_specific_heat(self) -> None:
        settings = Phase1Parameters()
        with self.assertRaises(ValueError):
            temperature_derivative(
                temperature_k=settings.initial_temperature_k,
                mass_kg=0.0,
                specific_heat_j_per_kg_k=settings.specific_heat_j_per_kg_k,
                absorptivity=settings.absorptivity,
                projected_area_m2=settings.projected_area_m2,
                solar_flux_w_per_m2=settings.solar_flux_w_per_m2,
                internal_heat_w=settings.internal_heat_w,
                emissivity=settings.emissivity,
                radiating_area_m2=settings.radiating_area_m2,
            )
        with self.assertRaises(ValueError):
            temperature_derivative(
                temperature_k=settings.initial_temperature_k,
                mass_kg=settings.mass_kg,
                specific_heat_j_per_kg_k=-900.0,
                absorptivity=settings.absorptivity,
                projected_area_m2=settings.projected_area_m2,
                solar_flux_w_per_m2=settings.solar_flux_w_per_m2,
                internal_heat_w=settings.internal_heat_w,
                emissivity=settings.emissivity,
                radiating_area_m2=settings.radiating_area_m2,
            )

    def test_simulation_rejects_invalid_time_step_and_duration(self) -> None:
        with self.assertRaises(ValueError):
            simulate_continuous_sunlight(duration_s=10.0, time_step_s=0.0)
        with self.assertRaises(ValueError):
            simulate_continuous_sunlight(duration_s=-1.0, time_step_s=1.0)

    def test_parameters_reject_emissivity_outside_unit_interval(self) -> None:
        with self.assertRaises(ValueError):
            Phase1Parameters(emissivity=1.1).validated()


if __name__ == "__main__":
    unittest.main()
