"""Orbital period, shadow geometry, eclipse length, and eclipse solar heating."""

from __future__ import annotations

import math
import unittest

from satellite_thermal.heat_transfer import solar_heating, temperature_derivative
from satellite_thermal.orbit import (
    BETA_RAD,
    EARTH_RADIUS_M,
    GRAVITATIONAL_PARAMETER_M3_PER_S2,
    CircularOrbit,
    eclipse_and_sunlight_durations_s,
    in_cylindrical_earth_shadow,
    in_eclipse_at_time,
    orbital_period_s,
    orbital_radius_m,
    position_angle_rad,
    position_at_time_m,
    satellite_position_m,
    sun_direction,
)
from satellite_thermal.orbital_simulation import (
    eclipse_intervals_s,
    simulate_orbital_eclipse,
    solar_flux_w_per_m2,
)
from satellite_thermal.parameters import Phase1Parameters


def _independent_period_s() -> float:
    radius_m = 6_371_000.0 + 500_000.0
    mu = 3.986004418e14
    return 2.0 * math.pi * math.sqrt(radius_m**3 / mu)


def _independent_eclipse_s(period_s: float) -> float:
    """Cylindrical beta = 0 eclipse length: T * asin(R/r) / pi."""
    radius_ratio = 6_371_000.0 / (6_371_000.0 + 500_000.0)
    return period_s * math.asin(radius_ratio) / math.pi


class OrbitalPeriodTests(unittest.TestCase):
    def test_period_matches_the_independent_formula(self) -> None:
        period = orbital_period_s(CircularOrbit())
        expected = _independent_period_s()
        self.assertTrue(math.isclose(period, expected, rel_tol=0.0, abs_tol=1e-9))

    def test_period_is_about_95_minutes(self) -> None:
        minutes = orbital_period_s() / 60.0
        self.assertGreater(minutes, 94.0)
        self.assertLess(minutes, 96.0)
        self.assertTrue(math.isclose(minutes, 95.0, rel_tol=0.0, abs_tol=1.0))

    def test_radius_uses_500_km_and_the_specified_earth_radius(self) -> None:
        orbit = CircularOrbit().validated()
        self.assertEqual(orbit.altitude_m, 500_000.0)
        self.assertEqual(orbit.earth_radius_m, EARTH_RADIUS_M)
        self.assertEqual(orbit.gravitational_parameter_m3_per_s2, GRAVITATIONAL_PARAMETER_M3_PER_S2)
        self.assertEqual(orbit.beta_rad, BETA_RAD)
        self.assertEqual(orbital_radius_m(orbit), 6_871_000.0)


class SunlightEclipseGeometryTests(unittest.TestCase):
    def test_angle_starts_sunward_and_advances_one_revolution_per_period(self) -> None:
        period = _independent_period_s()
        self.assertEqual(position_angle_rad(0.0, period), 0.0)
        self.assertTrue(math.isclose(position_angle_rad(period, period), 2.0 * math.pi, rel_tol=0.0, abs_tol=1e-12))
        self.assertTrue(
            math.isclose(position_angle_rad(0.5 * period, period), math.pi, rel_tol=0.0, abs_tol=1e-12)
        )

    def test_start_is_sunlit_and_antisun_point_is_in_eclipse(self) -> None:
        orbit = CircularOrbit()
        period = orbital_period_s(orbit)
        radius = orbital_radius_m(orbit)
        start = position_at_time_m(0.0, orbit)
        antisun = position_at_time_m(0.5 * period, orbit)
        self.assertTrue(math.isclose(start[0], radius, rel_tol=0.0, abs_tol=1e-6))
        self.assertTrue(math.isclose(start[1], 0.0, rel_tol=0.0, abs_tol=1e-6))
        self.assertEqual(start[2], 0.0)
        self.assertTrue(math.isclose(antisun[0], -radius, rel_tol=0.0, abs_tol=1e-6))
        self.assertFalse(in_eclipse_at_time(0.0, orbit))
        self.assertTrue(in_eclipse_at_time(0.5 * period, orbit))
        self.assertEqual(sun_direction(0.0), (1.0, 0.0, 0.0))

    def test_shadow_cylinder_uses_the_night_side_and_earth_radius(self) -> None:
        earth_radius = EARTH_RADIUS_M
        sun = (1.0, 0.0, 0.0)
        self.assertTrue(in_cylindrical_earth_shadow((-7_000_000.0, 0.0, 0.0), earth_radius, sun))
        self.assertFalse(
            in_cylindrical_earth_shadow((-7_000_000.0, earth_radius + 1_000.0, 0.0), earth_radius, sun)
        )
        self.assertFalse(in_cylindrical_earth_shadow((7_000_000.0, 0.0, 0.0), earth_radius, sun))
        self.assertFalse(in_cylindrical_earth_shadow((0.0, -7_000_000.0, 0.0), earth_radius, sun))

    def test_quarter_orbit_position_is_on_the_y_axis(self) -> None:
        radius = 6_871_000.0
        position = satellite_position_m(0.5 * math.pi, radius)
        self.assertTrue(math.isclose(position[0], 0.0, abs_tol=1e-8))
        self.assertTrue(math.isclose(position[1], radius, rel_tol=0.0, abs_tol=1e-6))
        self.assertEqual(position[2], 0.0)


class EclipseDurationTests(unittest.TestCase):
    def test_duration_comes_from_the_shadow_test_and_is_physically_plausible(self) -> None:
        orbit = CircularOrbit()
        time_step_s = 1.0
        eclipse_s, sunlight_s = eclipse_and_sunlight_durations_s(time_step_s, orbit)
        period = orbital_period_s(orbit)
        expected = _independent_eclipse_s(period)
        self.assertTrue(math.isclose(eclipse_s + sunlight_s, period, rel_tol=0.0, abs_tol=1e-6))
        self.assertTrue(math.isclose(eclipse_s, expected, rel_tol=0.0, abs_tol=2.0 * time_step_s))
        self.assertGreater(eclipse_s / 60.0, 30.0)
        self.assertLess(eclipse_s / 60.0, 45.0)
        self.assertGreater(sunlight_s, eclipse_s)

    def test_five_orbits_contain_five_eclipse_intervals(self) -> None:
        result = simulate_orbital_eclipse(orbit_count=5, time_step_s=30.0)
        intervals = eclipse_intervals_s(result.time_s, result.in_eclipse)
        self.assertEqual(len(intervals), 5)
        self.assertFalse(result.in_eclipse[0])
        self.assertGreater(result.eclipse_duration_s, 0.0)
        self.assertTrue(
            math.isclose(
                result.time_s[-1],
                5.0 * result.period_s,
                rel_tol=0.0,
                abs_tol=1e-6,
            )
        )


class EclipseSolarHeatingTests(unittest.TestCase):
    def test_solar_flux_and_heating_are_zero_in_eclipse(self) -> None:
        orbit = CircularOrbit()
        thermal = Phase1Parameters()
        eclipse_time = 0.5 * orbital_period_s(orbit)
        self.assertTrue(in_eclipse_at_time(eclipse_time, orbit))
        flux = solar_flux_w_per_m2(eclipse_time, orbit, thermal)
        self.assertEqual(flux, 0.0)
        self.assertEqual(
            solar_heating(thermal.absorptivity, thermal.projected_area_m2, flux),
            0.0,
        )
        eclipse_rate = temperature_derivative(
            temperature_k=thermal.initial_temperature_k,
            mass_kg=thermal.mass_kg,
            specific_heat_j_per_kg_k=thermal.specific_heat_j_per_kg_k,
            absorptivity=thermal.absorptivity,
            projected_area_m2=thermal.projected_area_m2,
            solar_flux_w_per_m2=flux,
            internal_heat_w=thermal.internal_heat_w,
            emissivity=thermal.emissivity,
            radiating_area_m2=thermal.radiating_area_m2,
        )
        zero_flux_rate = temperature_derivative(
            temperature_k=thermal.initial_temperature_k,
            mass_kg=thermal.mass_kg,
            specific_heat_j_per_kg_k=thermal.specific_heat_j_per_kg_k,
            absorptivity=thermal.absorptivity,
            projected_area_m2=thermal.projected_area_m2,
            solar_flux_w_per_m2=0.0,
            internal_heat_w=thermal.internal_heat_w,
            emissivity=thermal.emissivity,
            radiating_area_m2=thermal.radiating_area_m2,
        )
        self.assertEqual(eclipse_rate, zero_flux_rate)

    def test_solar_flux_at_the_subsolar_start_is_the_phase1_value(self) -> None:
        thermal = Phase1Parameters()
        flux = solar_flux_w_per_m2(0.0, CircularOrbit(), thermal)
        self.assertEqual(flux, 1361.0)
        self.assertTrue(
            math.isclose(
                solar_heating(thermal.absorptivity, thermal.projected_area_m2, flux),
                8.166,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        )

    def test_stored_flags_match_the_geometry_and_eclipse_steps_use_zero_flux(self) -> None:
        result = simulate_orbital_eclipse(orbit_count=1, time_step_s=20.0)
        orbit = CircularOrbit()
        thermal = Phase1Parameters()
        for time_s, flag in zip(result.time_s, result.in_eclipse):
            self.assertEqual(flag, in_eclipse_at_time(time_s, orbit))
            flux = solar_flux_w_per_m2(time_s, orbit, thermal)
            if flag:
                self.assertEqual(flux, 0.0)
            else:
                self.assertEqual(flux, thermal.solar_flux_w_per_m2)
