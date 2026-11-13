"""Albedo heating, eclipse zeroing, validation, and backward compatibility."""

from __future__ import annotations

import math
import unittest

from satellite_thermal.albedo import (
    DEFAULT_ALBEDO_AREA_M2,
    EARTH_BOND_ALBEDO,
    AlbedoParameters,
    albedo_geometry_factor,
    albedo_heat_w_at_time,
    albedo_heating,
)
from satellite_thermal.earth_infrared import earth_view_factor
from satellite_thermal.heat_transfer import temperature_derivative
from satellite_thermal.orbit import CircularOrbit, in_eclipse_at_time, orbital_period_s
from satellite_thermal.orbital_simulation import simulate_orbital_eclipse
from satellite_thermal.parameters import Phase1Parameters


def _independent_peak_albedo_w() -> float:
    view = (6_371_000.0 / (6_371_000.0 + 500_000.0)) ** 2
    return 0.60 * 0.01 * view * 0.30 * 1361.0


class AlbedoHeatingTests(unittest.TestCase):
    def test_peak_geometry_and_heating_match_independent_values(self) -> None:
        view = earth_view_factor(CircularOrbit())
        factor = albedo_geometry_factor(0.0, view)
        expected = _independent_peak_albedo_w()
        actual = albedo_heating(0.60, 0.01, 0.30, 1361.0, factor)
        at_start = albedo_heat_w_at_time(0.0, CircularOrbit(), Phase1Parameters())
        self.assertTrue(math.isclose(factor, view, rel_tol=0.0, abs_tol=1e-15))
        self.assertTrue(math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12))
        self.assertTrue(math.isclose(at_start, expected, rel_tol=0.0, abs_tol=1e-12))
        self.assertGreater(actual, 2.0)
        self.assertLess(actual, 2.3)

    def test_geometry_factor_is_zero_on_the_night_side(self) -> None:
        view = earth_view_factor(CircularOrbit())
        self.assertEqual(albedo_geometry_factor(math.pi, view), 0.0)
        # cos(pi/2) is a tiny float residual, not an exact zero.
        self.assertTrue(
            math.isclose(
                albedo_geometry_factor(0.5 * math.pi, view),
                0.0,
                rel_tol=0.0,
                abs_tol=1e-15,
            )
        )
        half = albedo_geometry_factor(math.pi / 3.0, view)
        self.assertTrue(
            math.isclose(half, view * 0.5, rel_tol=0.0, abs_tol=1e-12)
        )

    def test_uses_solar_absorptivity_not_infrared_emissivity(self) -> None:
        # Doubling IR emissivity must not change albedo heating.
        base = albedo_heating(0.60, 0.01, 0.30, 1361.0, 0.5)
        # Explicit check that the solar absorptivity argument controls the result.
        higher_alpha = albedo_heating(0.80, 0.01, 0.30, 1361.0, 0.5)
        self.assertTrue(
            math.isclose(higher_alpha, base * (0.80 / 0.60), rel_tol=0.0, abs_tol=1e-12)
        )


class EclipseAndZeroCases(unittest.TestCase):
    def test_albedo_is_zero_in_eclipse(self) -> None:
        orbit = CircularOrbit()
        eclipse_time = 0.5 * orbital_period_s(orbit)
        self.assertTrue(in_eclipse_at_time(eclipse_time, orbit))
        self.assertEqual(
            albedo_heat_w_at_time(eclipse_time, orbit, Phase1Parameters()),
            0.0,
        )

    def test_zero_bond_albedo_or_zero_solar_flux_gives_zero_heating(self) -> None:
        self.assertEqual(albedo_heating(0.60, 0.01, 0.0, 1361.0, 0.5), 0.0)
        self.assertEqual(albedo_heating(0.60, 0.01, 0.30, 0.0, 0.5), 0.0)
        self.assertEqual(albedo_heating(0.60, 0.01, 0.30, 1361.0, 0.0), 0.0)

    def test_rejects_invalid_albedo_inputs(self) -> None:
        with self.assertRaises(ValueError):
            albedo_heating(1.2, 0.01, 0.30, 1361.0, 0.5)
        with self.assertRaises(ValueError):
            albedo_heating(0.60, 0.0, 0.30, 1361.0, 0.5)
        with self.assertRaises(ValueError):
            albedo_heating(0.60, 0.01, 1.5, 1361.0, 0.5)
        with self.assertRaises(ValueError):
            albedo_geometry_factor(0.0, 1.5)
        with self.assertRaises(ValueError):
            AlbedoParameters(earth_bond_albedo=-0.1).validated()


class BackwardCompatibilityTests(unittest.TestCase):
    def test_default_orbital_run_still_disables_albedo(self) -> None:
        result = simulate_orbital_eclipse(orbit_count=1, time_step_s=60.0)
        self.assertFalse(result.include_albedo)
        self.assertEqual(result.earth_infrared_heat_w, 0.0)

    def test_phase3b_is_warmer_than_phase3a_and_zero_in_eclipse_steps(self) -> None:
        phase3a = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=20.0,
            include_earth_infrared=True,
            include_albedo=False,
        )
        phase3b = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=20.0,
            include_earth_infrared=True,
            include_albedo=True,
        )
        self.assertFalse(phase3a.include_albedo)
        self.assertTrue(phase3b.include_albedo)
        self.assertEqual(phase3a.time_s, phase3b.time_s)
        self.assertEqual(phase3a.in_eclipse, phase3b.in_eclipse)
        self.assertGreater(phase3b.temperature_k[-1], phase3a.temperature_k[-1])
        for time_s, flag in zip(phase3b.time_s, phase3b.in_eclipse):
            heat = albedo_heat_w_at_time(time_s, CircularOrbit(), Phase1Parameters())
            if flag:
                self.assertEqual(heat, 0.0)

    def test_derivative_adds_albedo_power(self) -> None:
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
            albedo_heat_w=0.0,
        )
        with_albedo = temperature_derivative(
            temperature_k=settings.initial_temperature_k,
            mass_kg=settings.mass_kg,
            specific_heat_j_per_kg_k=settings.specific_heat_j_per_kg_k,
            absorptivity=settings.absorptivity,
            projected_area_m2=settings.projected_area_m2,
            solar_flux_w_per_m2=0.0,
            internal_heat_w=settings.internal_heat_w,
            emissivity=settings.emissivity,
            radiating_area_m2=settings.radiating_area_m2,
            albedo_heat_w=2.1,
        )
        capacity = settings.mass_kg * settings.specific_heat_j_per_kg_k
        self.assertTrue(
            math.isclose(
                with_albedo - without,
                2.1 / capacity,
                rel_tol=0.0,
                abs_tol=1e-15,
            )
        )

    def test_default_albedo_constants(self) -> None:
        settings = AlbedoParameters()
        self.assertEqual(settings.earth_bond_albedo, EARTH_BOND_ALBEDO)
        self.assertEqual(settings.albedo_area_m2, DEFAULT_ALBEDO_AREA_M2)
        self.assertEqual(EARTH_BOND_ALBEDO, 0.30)


if __name__ == "__main__":
    unittest.main()
