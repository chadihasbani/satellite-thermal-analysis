"""Earth infrared heating, validation, and Phase 2 backward compatibility."""

from __future__ import annotations

import math
import unittest

from satellite_thermal.earth_infrared import (
    DEFAULT_EARTH_FACING_AREA_M2,
    DEFAULT_INFRARED_ABSORPTIVITY,
    EARTH_OLR_W_PER_M2,
    EarthInfraredParameters,
    earth_infrared_heat_w,
    earth_infrared_heating,
    earth_view_factor,
)
from satellite_thermal.heat_transfer import temperature_derivative
from satellite_thermal.orbit import CircularOrbit, EARTH_RADIUS_M
from satellite_thermal.orbital_simulation import simulate_orbital_eclipse
from satellite_thermal.parameters import Phase1Parameters


def _independent_view_factor() -> float:
    radius_orbit_m = EARTH_RADIUS_M + 500_000.0
    return (EARTH_RADIUS_M / radius_orbit_m) ** 2


def _independent_earth_ir_w() -> float:
    return (
        DEFAULT_INFRARED_ABSORPTIVITY
        * DEFAULT_EARTH_FACING_AREA_M2
        * _independent_view_factor()
        * EARTH_OLR_W_PER_M2
    )


class EarthInfraredHeatingTests(unittest.TestCase):
    def test_view_factor_matches_radius_ratio_squared(self) -> None:
        factor = earth_view_factor(CircularOrbit())
        expected = _independent_view_factor()
        self.assertTrue(math.isclose(factor, expected, rel_tol=0.0, abs_tol=1e-15))
        self.assertGreater(factor, 0.85)
        self.assertLess(factor, 0.87)

    def test_heating_matches_the_independent_product(self) -> None:
        factor = _independent_view_factor()
        expected = _independent_earth_ir_w()
        actual = earth_infrared_heating(
            infrared_absorptivity=0.80,
            earth_facing_area_m2=0.01,
            earth_olr_w_per_m2=240.0,
            view_factor=factor,
        )
        from_helpers = earth_infrared_heat_w(CircularOrbit(), EarthInfraredParameters())
        self.assertTrue(math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12))
        self.assertTrue(math.isclose(from_helpers, expected, rel_tol=0.0, abs_tol=1e-12))
        self.assertGreater(actual, 1.5)
        self.assertLess(actual, 1.8)

    def test_heating_scales_linearly_with_olr_and_area(self) -> None:
        factor = 0.5
        base = earth_infrared_heating(0.80, 0.01, 240.0, factor)
        doubled_olr = earth_infrared_heating(0.80, 0.01, 480.0, factor)
        doubled_area = earth_infrared_heating(0.80, 0.02, 240.0, factor)
        self.assertTrue(math.isclose(doubled_olr, 2.0 * base, rel_tol=0.0, abs_tol=1e-12))
        self.assertTrue(math.isclose(doubled_area, 2.0 * base, rel_tol=0.0, abs_tol=1e-12))


class ZeroFluxAndValidationTests(unittest.TestCase):
    def test_zero_olr_or_zero_view_factor_gives_zero_heating(self) -> None:
        self.assertEqual(earth_infrared_heating(0.80, 0.01, 0.0, 0.5), 0.0)
        self.assertEqual(earth_infrared_heating(0.80, 0.01, 240.0, 0.0), 0.0)

    def test_rejects_invalid_absorptivity_area_and_view_factor(self) -> None:
        with self.assertRaises(ValueError):
            earth_infrared_heating(1.2, 0.01, 240.0, 0.5)
        with self.assertRaises(ValueError):
            earth_infrared_heating(0.80, 0.0, 240.0, 0.5)
        with self.assertRaises(ValueError):
            earth_infrared_heating(0.80, 0.01, 240.0, 1.5)
        with self.assertRaises(ValueError):
            EarthInfraredParameters(infrared_absorptivity=-0.1).validated()
        with self.assertRaises(ValueError):
            EarthInfraredParameters(earth_olr_w_per_m2=-1.0).validated()

    def test_derivative_includes_earth_ir_when_supplied(self) -> None:
        settings = Phase1Parameters()
        without = temperature_derivative(
            temperature_k=settings.initial_temperature_k,
            mass_kg=settings.mass_kg,
            specific_heat_j_per_kg_k=settings.specific_heat_j_per_kg_k,
            absorptivity=settings.absorptivity,
            projected_area_m2=settings.projected_area_m2,
            solar_flux_w_per_m2=0.0,
            internal_heat_w=settings.internal_heat_w,
            emissivity=settings.emissivity,
            radiating_area_m2=settings.radiating_area_m2,
            earth_infrared_heat_w=0.0,
        )
        with_ir = temperature_derivative(
            temperature_k=settings.initial_temperature_k,
            mass_kg=settings.mass_kg,
            specific_heat_j_per_kg_k=settings.specific_heat_j_per_kg_k,
            absorptivity=settings.absorptivity,
            projected_area_m2=settings.projected_area_m2,
            solar_flux_w_per_m2=0.0,
            internal_heat_w=settings.internal_heat_w,
            emissivity=settings.emissivity,
            radiating_area_m2=settings.radiating_area_m2,
            earth_infrared_heat_w=1.65,
        )
        capacity = settings.mass_kg * settings.specific_heat_j_per_kg_k
        self.assertTrue(
            math.isclose(with_ir - without, 1.65 / capacity, rel_tol=0.0, abs_tol=1e-15)
        )


class BackwardCompatibilityTests(unittest.TestCase):
    def test_default_orbital_run_still_has_zero_earth_ir(self) -> None:
        result = simulate_orbital_eclipse(orbit_count=1, time_step_s=60.0)
        self.assertEqual(result.earth_infrared_heat_w, 0.0)

    def test_phase3a_flag_adds_constant_earth_ir_in_sunlight_and_eclipse(self) -> None:
        expected = _independent_earth_ir_w()
        without = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=30.0,
            include_earth_infrared=False,
        )
        with_ir = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=30.0,
            include_earth_infrared=True,
        )
        self.assertEqual(without.earth_infrared_heat_w, 0.0)
        self.assertTrue(
            math.isclose(with_ir.earth_infrared_heat_w, expected, rel_tol=0.0, abs_tol=1e-12)
        )
        self.assertEqual(without.time_s, with_ir.time_s)
        self.assertEqual(without.in_eclipse, with_ir.in_eclipse)
        self.assertTrue(any(with_ir.in_eclipse))
        self.assertTrue(any(not flag for flag in with_ir.in_eclipse))
        # Extra absorbed heat keeps the Earth-IR case warmer after one orbit.
        self.assertGreater(with_ir.temperature_k[-1], without.temperature_k[-1])

    def test_phase1_parameters_are_unchanged(self) -> None:
        settings = Phase1Parameters()
        self.assertEqual(settings.mass_kg, 5.0)
        self.assertEqual(settings.projected_area_m2, 0.01)
        self.assertEqual(settings.radiating_area_m2, 0.06)
        self.assertEqual(settings.absorptivity, 0.60)
        self.assertEqual(settings.emissivity, 0.80)
        self.assertEqual(settings.internal_heat_w, 5.0)
        self.assertEqual(settings.solar_flux_w_per_m2, 1361.0)


if __name__ == "__main__":
    unittest.main()
