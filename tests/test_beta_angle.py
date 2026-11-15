"""Independent verification of variable orbital beta and eclipse geometry."""

from __future__ import annotations

import math
import unittest

from satellite_thermal.orbit import (
    EARTH_RADIUS_M,
    CircularOrbit,
    analytical_eclipse_duration_s,
    critical_beta_rad,
    eclipse_and_sunlight_durations_s,
    in_cylindrical_earth_shadow,
    in_eclipse_at_time,
    orbital_period_s,
    orbital_radius_m,
    satellite_position_m,
    sun_direction,
)
from satellite_thermal.orbit_3d import _shadow_cylinder_mesh
from satellite_thermal.orbital_simulation import simulate_orbital_eclipse
from satellite_thermal.parameters import Phase1Parameters


def _independent_beta_critical_rad(earth_radius_m: float, orbital_radius: float) -> float:
    """Critical beta from night-side cylinder tangency, without calling project helpers.

    At theta = pi, |r × s| = r |sin(beta)|. Tangency requires r |sin(beta)| = R,
    so |beta|_crit = asin(R/r). This intentionally uses asin, not acos.
    """
    return math.asin(earth_radius_m / orbital_radius)


def _independent_analytical_eclipse_s(
    period_s: float,
    earth_radius_m: float,
    orbital_radius: float,
    beta_rad: float,
) -> float:
    """Closed-form eclipse duration from the cylindrical |r × s| inequality."""
    ratio = earth_radius_m / orbital_radius
    sin_b = math.sin(beta_rad)
    if abs(sin_b) >= ratio:
        return 0.0
    cos_b = math.cos(beta_rad)
    kappa = math.sqrt((ratio * ratio - sin_b * sin_b) / (cos_b * cos_b))
    kappa = min(1.0, kappa)
    return (period_s / math.pi) * math.asin(kappa)


class CriticalBetaGeometryTests(unittest.TestCase):
    def test_critical_beta_is_asin_not_acos_at_500_km(self) -> None:
        orbit = CircularOrbit().validated()
        radius = orbital_radius_m(orbit)
        independent = _independent_beta_critical_rad(EARTH_RADIUS_M, radius)
        implemented = critical_beta_rad(orbit)
        self.assertTrue(math.isclose(implemented, independent, abs_tol=1e-12))
        degrees = math.degrees(implemented)
        # ~68°, not the complementary acos(R/r) ≈ 22°.
        self.assertGreater(degrees, 67.5)
        self.assertLess(degrees, 68.5)
        acos_complement_deg = math.degrees(math.acos(EARTH_RADIUS_M / radius))
        self.assertGreater(abs(degrees - acos_complement_deg), 40.0)

    def test_antisun_tangency_marks_the_critical_boundary(self) -> None:
        """Independent discrete check: antisun in cylinder iff |sin beta| <= R/r."""
        orbit = CircularOrbit().validated()
        radius = orbital_radius_m(orbit)
        antisun = satellite_position_m(math.pi, radius)
        ratio = EARTH_RADIUS_M / radius
        beta_c = math.asin(ratio)
        for offset_deg, expect_eclipse in (
            (-1.0, True),
            (0.0, True),  # equality included by |r × s| <= R
            (1.0, False),
        ):
            beta = beta_c + math.radians(offset_deg)
            sun = sun_direction(beta)
            in_shadow = in_cylindrical_earth_shadow(antisun, EARTH_RADIUS_M, sun)
            self.assertEqual(in_shadow, expect_eclipse, msg=f"offset_deg={offset_deg}")


class BetaEclipseDurationTests(unittest.TestCase):
    def test_beta_zero_matches_legacy_closed_form(self) -> None:
        orbit = CircularOrbit(beta_rad=0.0).validated()
        period = orbital_period_s(orbit)
        expected = period * math.asin(EARTH_RADIUS_M / orbital_radius_m(orbit)) / math.pi
        self.assertTrue(
            math.isclose(analytical_eclipse_duration_s(orbit), expected, abs_tol=1e-9)
        )

    def test_eclipse_duration_table_analytical_vs_numerical(self) -> None:
        time_step_s = 1.0
        period0 = orbital_period_s(CircularOrbit())
        cases = (0.0, 30.0, 60.0, 68.0, 75.0, -30.0)
        durations_by_abs_beta: dict[float, float] = {}
        for beta_deg in cases:
            orbit = CircularOrbit(beta_rad=math.radians(beta_deg)).validated()
            self.assertTrue(
                math.isclose(orbital_period_s(orbit), period0, abs_tol=1e-9),
                msg="period must be independent of beta",
            )
            analytical = analytical_eclipse_duration_s(orbit)
            independent = _independent_analytical_eclipse_s(
                period0,
                EARTH_RADIUS_M,
                orbital_radius_m(orbit),
                math.radians(beta_deg),
            )
            numerical, sunlight = eclipse_and_sunlight_durations_s(time_step_s, orbit)
            self.assertTrue(math.isclose(analytical, independent, abs_tol=1e-9))
            self.assertTrue(
                math.isclose(numerical, analytical, abs_tol=2.0 * time_step_s),
                msg=f"beta={beta_deg}: num={numerical}, ana={analytical}",
            )
            self.assertTrue(
                math.isclose(numerical + sunlight, period0, abs_tol=1e-6)
            )
            abs_beta = abs(beta_deg)
            if abs_beta in durations_by_abs_beta:
                self.assertTrue(
                    math.isclose(
                        durations_by_abs_beta[abs_beta],
                        analytical,
                        abs_tol=1e-12,
                    ),
                    msg="±beta must share eclipse duration",
                )
            else:
                durations_by_abs_beta[abs_beta] = analytical

        # Duration decreases as |beta| increases.
        ordered = sorted(durations_by_abs_beta.items())
        for index in range(1, len(ordered)):
            self.assertLessEqual(ordered[index][1], ordered[index - 1][1] + 1e-9)

        beta_c = critical_beta_rad(CircularOrbit())
        just_below = CircularOrbit(beta_rad=beta_c - math.radians(0.05)).validated()
        just_above = CircularOrbit(beta_rad=beta_c + math.radians(0.05)).validated()
        self.assertGreater(analytical_eclipse_duration_s(just_below), 0.0)
        self.assertEqual(analytical_eclipse_duration_s(just_above), 0.0)
        self.assertEqual(analytical_eclipse_duration_s(CircularOrbit(beta_rad=beta_c)), 0.0)
        num_above, _ = eclipse_and_sunlight_durations_s(1.0, just_above)
        self.assertEqual(num_above, 0.0)

    def test_sun_direction_uses_same_beta_convention(self) -> None:
        self.assertEqual(sun_direction(0.0), (1.0, 0.0, 0.0))
        beta = math.radians(30.0)
        sx, sy, sz = sun_direction(beta)
        self.assertTrue(math.isclose(sx, math.cos(beta), abs_tol=1e-12))
        self.assertEqual(sy, 0.0)
        self.assertTrue(math.isclose(sz, math.sin(beta), abs_tol=1e-12))
        # Positive and negative beta flip the out-of-plane component only.
        sx_n, sy_n, sz_n = sun_direction(-beta)
        self.assertTrue(math.isclose(sx_n, sx, abs_tol=1e-12))
        self.assertEqual(sy_n, 0.0)
        self.assertTrue(math.isclose(sz_n, -sz, abs_tol=1e-12))


class ContinuousSunlightThermalTests(unittest.TestCase):
    def test_high_beta_simulation_has_no_eclipse_flags(self) -> None:
        orbit = CircularOrbit(beta_rad=math.radians(75.0)).validated()
        result = simulate_orbital_eclipse(
            parameters=Phase1Parameters(),
            orbit=orbit,
            orbit_count=1,
            time_step_s=10.0,
        )
        self.assertFalse(any(result.in_eclipse))
        self.assertEqual(result.eclipse_duration_s, 0.0)
        self.assertFalse(in_eclipse_at_time(0.5 * result.period_s, orbit))


class ShadowVisualizationTests(unittest.TestCase):
    def test_umbra_mesh_extends_anti_sun_for_nonzero_beta(self) -> None:
        beta = math.radians(40.0)
        sun = sun_direction(beta)
        xs, ys, zs = _shadow_cylinder_mesh(
            EARTH_RADIUS_M,
            length_m=1.0e7,
            sun_direction_vector=sun,
            n_theta=8,
            n_axial=4,
        )
        # Far end of the cylinder should lie near the anti-sun axis.
        # Exclude the duplicated closing sample of each ring.
        n_unique = len(xs[-1]) - 1
        end_x = sum(xs[-1][:n_unique]) / n_unique
        end_y = sum(ys[-1][:n_unique]) / n_unique
        end_z = sum(zs[-1][:n_unique]) / n_unique
        end = (end_x, end_y, end_z)
        end_mag = math.sqrt(sum(c * c for c in end))
        anti = (-sun[0], -sun[1], -sun[2])
        unit_end = tuple(c / end_mag for c in end)
        for component, expected in zip(unit_end, anti):
            self.assertTrue(math.isclose(component, expected, abs_tol=1e-9))

    def test_shadow_and_eclipse_state_at_zero_sixty_seventy_five(self) -> None:
        from satellite_thermal.orbit_3d import build_orbit_3d_figure
        from satellite_thermal.orbital_simulation import simulate_orbital_eclipse

        for beta_deg, expect_any_eclipse, expect_antisun_eclipse in (
            (0.0, True, True),
            (60.0, True, True),
            (75.0, False, False),
        ):
            orbit = CircularOrbit(beta_rad=math.radians(beta_deg)).validated()
            result = simulate_orbital_eclipse(
                parameters=Phase1Parameters(),
                orbit=orbit,
                orbit_count=1,
                time_step_s=10.0,
            )
            self.assertEqual(any(result.in_eclipse), expect_any_eclipse)
            self.assertEqual(
                in_eclipse_at_time(0.5 * result.period_s, orbit),
                expect_antisun_eclipse,
            )
            sun = sun_direction(orbit.beta_rad)
            xs, ys, zs = _shadow_cylinder_mesh(
                EARTH_RADIUS_M,
                length_m=1.0e7,
                sun_direction_vector=sun,
                n_theta=12,
                n_axial=4,
            )
            n_unique = len(xs[-1]) - 1
            end = (
                sum(xs[-1][:n_unique]) / n_unique,
                sum(ys[-1][:n_unique]) / n_unique,
                sum(zs[-1][:n_unique]) / n_unique,
            )
            mag = math.sqrt(sum(c * c for c in end))
            unit = tuple(c / mag for c in end)
            anti = (-sun[0], -sun[1], -sun[2])
            for component, expected in zip(unit, anti):
                self.assertTrue(math.isclose(component, expected, abs_tol=1e-9))
            figure = build_orbit_3d_figure(result, orbit, 0)
            names = [trace.name for trace in figure.data]
            self.assertNotIn("Sun direction", names)
            self.assertIn("Eclipse shadow", names)
            self.assertEqual(figure.layout.scene.dragmode, "turntable")


if __name__ == "__main__":
    unittest.main()
