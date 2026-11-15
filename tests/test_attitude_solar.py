"""Independent geometric checks for attitude-dependent solar heating."""

from __future__ import annotations

import math
import unittest

from satellite_thermal.attitude import (
    AttitudeMode,
    body_axes_inertial,
    orbital_basis,
)
from satellite_thermal.gui_support import (
    GuiRunRequest,
    all_curves,
    default_gui_request,
    run_baseline_comparison_mode,
    run_environment_comparison_mode,
    run_single_mode,
    temperature_metrics_c,
)
from satellite_thermal.orbit import CircularOrbit, sun_direction
from satellite_thermal.orbital_simulation import simulate_orbital_eclipse
from satellite_thermal.parameters import Phase1Parameters, STEFAN_BOLTZMANN
from satellite_thermal.spacecraft_geometry import (
    FACE_NAMES,
    RectangularBusGeometry,
    face_normal_inertial,
)
from satellite_thermal.surface_heating import (
    face_solar_cosine,
    projected_solar_area_m2,
    surface_radiative_cooling_w,
    surface_solar_heating_w,
)


def _independent_dot(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


class GeometryAreaTests(unittest.TestCase):
    def test_face_areas_from_dimensions_without_double_counting(self) -> None:
        geom = RectangularBusGeometry(length_m=0.3, width_m=0.1, height_m=0.1)
        self.assertAlmostEqual(geom.face_area_m2("+x"), 0.01)
        self.assertAlmostEqual(geom.face_area_m2("-x"), 0.01)
        self.assertAlmostEqual(geom.face_area_m2("+y"), 0.03)
        self.assertAlmostEqual(geom.face_area_m2("+z"), 0.03)
        self.assertAlmostEqual(geom.total_exterior_area_m2(), 0.14)
        summed = sum(geom.face_area_m2(name) for name in FACE_NAMES)
        self.assertAlmostEqual(summed, geom.total_exterior_area_m2())

    def test_default_cube_matches_legacy_area_defaults(self) -> None:
        geom = RectangularBusGeometry()
        self.assertAlmostEqual(geom.face_area_m2("+x"), 0.01)
        self.assertAlmostEqual(geom.total_exterior_area_m2(), 0.06)


class SunVectorAndProjectedAreaTests(unittest.TestCase):
    def test_sun_direction_convention_before_dot_products(self) -> None:
        # Beta = 0 => s = +X, matching the cylindrical eclipse night-side test.
        self.assertEqual(sun_direction(0.0), (1.0, 0.0, 0.0))
        sun = sun_direction(math.radians(30.0))
        self.assertAlmostEqual(sun[0], math.cos(math.radians(30.0)))
        self.assertEqual(sun[1], 0.0)
        self.assertAlmostEqual(sun[2], math.sin(math.radians(30.0)))

    def test_independent_illumination_cases_on_unit_cube(self) -> None:
        geom = RectangularBusGeometry(length_m=1.0, width_m=1.0, height_m=1.0)
        body_x = (1.0, 0.0, 0.0)
        body_y = (0.0, 1.0, 0.0)
        body_z = (0.0, 0.0, 1.0)
        sun = (1.0, 0.0, 0.0)
        # Direct Sun-facing +X: cos = 1
        n_plus = face_normal_inertial(geom, "+x", body_x, body_y, body_z)
        self.assertAlmostEqual(face_solar_cosine(n_plus, sun), 1.0)
        # Perpendicular +Y: cos = 0
        n_y = face_normal_inertial(geom, "+y", body_x, body_y, body_z)
        self.assertAlmostEqual(face_solar_cosine(n_y, sun), 0.0)
        # Back-facing -X: cos clamped to 0
        n_minus = face_normal_inertial(geom, "-x", body_x, body_y, body_z)
        self.assertAlmostEqual(face_solar_cosine(n_minus, sun), 0.0)
        # Multi-face: sun along (1,1,0)/sqrt(2) illuminates +X and +Y equally.
        sun2 = (1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0), 0.0)
        area = projected_solar_area_m2(geom, body_x, body_y, body_z, sun2)
        # Independent: 1*cos45 + 1*cos45 = sqrt(2)
        self.assertAlmostEqual(area, math.sqrt(2.0), places=12)
        q = surface_solar_heating_w(
            geom, body_x, body_y, body_z, sun2, solar_flux_w_per_m2=1000.0
        )
        # alpha=0.6 default
        self.assertAlmostEqual(q, 0.6 * 1000.0 * math.sqrt(2.0), places=9)

    def test_eclipse_flux_zero_forces_zero_solar(self) -> None:
        geom = RectangularBusGeometry()
        q = surface_solar_heating_w(
            geom,
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (1.0, 0.0, 0.0),
            solar_flux_w_per_m2=0.0,
        )
        self.assertEqual(q, 0.0)

    def test_cube_projected_area_bounds_and_solar_power(self) -> None:
        """Cube projected area lies between one face and the space-diagonal bound.

        Face-on: A_proj = 0.01 m² → Q = 0.6 * 1361 * 0.01 = 8.166 W
        Space diagonal: A_proj = √3 * 0.01 m² → Q ≈ 14.144 W
        """
        geom = RectangularBusGeometry()
        body = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        face_sun = (1.0, 0.0, 0.0)
        diag = tuple(component / math.sqrt(3.0) for component in (1.0, 1.0, 1.0))
        a_face = projected_solar_area_m2(geom, *body, face_sun)
        a_diag = projected_solar_area_m2(geom, *body, diag)
        self.assertAlmostEqual(a_face, 0.01, places=12)
        self.assertAlmostEqual(a_diag, math.sqrt(3.0) * 0.01, places=12)
        self.assertAlmostEqual(
            surface_solar_heating_w(geom, *body, face_sun, 1361.0),
            8.166,
            places=12,
        )
        self.assertAlmostEqual(
            surface_solar_heating_w(geom, *body, diag, 1361.0),
            0.6 * 1361.0 * math.sqrt(3.0) * 0.01,
            places=12,
        )


class AttitudeModeTests(unittest.TestCase):
    def test_orbital_basis_is_right_handed(self) -> None:
        r_hat, theta_hat, h_hat = orbital_basis(math.radians(40.0))
        cross = (
            r_hat[1] * theta_hat[2] - r_hat[2] * theta_hat[1],
            r_hat[2] * theta_hat[0] - r_hat[0] * theta_hat[2],
            r_hat[0] * theta_hat[1] - r_hat[1] * theta_hat[0],
        )
        for component, expected in zip(cross, h_hat):
            self.assertAlmostEqual(component, expected, places=12)

    def test_fixed_inertial_axes(self) -> None:
        x, y, z = body_axes_inertial(
            AttitudeMode.FIXED_INERTIAL, 1.2, sun_direction(0.0)
        )
        self.assertEqual(x, (1.0, 0.0, 0.0))
        self.assertEqual(y, (0.0, 1.0, 0.0))
        self.assertEqual(z, (0.0, 0.0, 1.0))

    def test_nadir_pointing_z_toward_earth(self) -> None:
        theta = math.radians(25.0)
        r_hat, theta_hat, _ = orbital_basis(theta)
        x, y, z = body_axes_inertial(
            AttitudeMode.NADIR_POINTING, theta, sun_direction(0.0)
        )
        for component, expected in zip(z, (-r_hat[0], -r_hat[1], -r_hat[2])):
            self.assertAlmostEqual(component, expected, places=12)
        for component, expected in zip(x, theta_hat):
            self.assertAlmostEqual(component, expected, places=12)
        # Right-handed triad.
        self.assertAlmostEqual(_independent_dot(x, y), 0.0, places=12)
        self.assertAlmostEqual(_independent_dot(y, z), 0.0, places=12)
        self.assertAlmostEqual(_independent_dot(z, x), 0.0, places=12)

    def test_sun_pointing_x_toward_sun(self) -> None:
        sun = sun_direction(math.radians(20.0))
        x, y, z = body_axes_inertial(AttitudeMode.SUN_POINTING, 0.7, sun)
        for component, expected in zip(x, sun):
            self.assertAlmostEqual(component, expected, places=12)
        self.assertAlmostEqual(_independent_dot(x, y), 0.0, places=12)
        self.assertAlmostEqual(_independent_dot(y, z), 0.0, places=12)
        self.assertAlmostEqual(math.sqrt(_independent_dot(z, z)), 1.0, places=12)

    def test_sun_pointing_singularity_near_orbit_normal(self) -> None:
        # Sun nearly along +Z: secondary reference must switch without crashing.
        sun = (1.0e-8, 0.0, 1.0)
        x, y, z = body_axes_inertial(AttitudeMode.SUN_POINTING, 0.0, sun)
        self.assertAlmostEqual(math.sqrt(_independent_dot(x, x)), 1.0, places=9)
        self.assertAlmostEqual(math.sqrt(_independent_dot(y, y)), 1.0, places=9)
        self.assertAlmostEqual(math.sqrt(_independent_dot(z, z)), 1.0, places=9)


class RadiationConsistencyTests(unittest.TestCase):
    def test_uniform_emissivity_matches_total_area_formula(self) -> None:
        geom = RectangularBusGeometry(
            length_m=0.2, width_m=0.1, height_m=0.1, emissivity=0.8
        )
        temperature_k = 300.0
        q = surface_radiative_cooling_w(geom, temperature_k)
        expected = (
            0.8
            * STEFAN_BOLTZMANN
            * geom.total_exterior_area_m2()
            * temperature_k**4
        )
        self.assertAlmostEqual(q, expected, places=12)


class LegacyEquivalenceTests(unittest.TestCase):
    def test_enhanced_fixed_inertial_cube_matches_legacy_beta_zero(self) -> None:
        """0.1 m cube, fixed inertial, β=0: one face sunlit → legacy solar/rad."""
        thermal = Phase1Parameters()
        orbit = CircularOrbit(beta_rad=0.0)
        legacy = simulate_orbital_eclipse(
            orbit_count=2,
            time_step_s=10.0,
            parameters=thermal,
            orbit=orbit,
            include_earth_infrared=True,
            include_albedo=True,
            thermal_model="legacy",
        )
        enhanced = simulate_orbital_eclipse(
            orbit_count=2,
            time_step_s=10.0,
            parameters=thermal,
            orbit=orbit,
            include_earth_infrared=True,
            include_albedo=True,
            thermal_model="enhanced",
            geometry=RectangularBusGeometry(
                length_m=0.1,
                width_m=0.1,
                height_m=0.1,
                absorptivity=thermal.absorptivity,
                emissivity=thermal.emissivity,
            ),
            attitude_mode=AttitudeMode.FIXED_INERTIAL,
        )
        for t_legacy, t_enh in zip(legacy.temperature_k, enhanced.temperature_k):
            self.assertTrue(math.isclose(t_legacy, t_enh, rel_tol=0.0, abs_tol=1e-9))


class GuiPropagationTests(unittest.TestCase):
    def test_enhanced_selections_propagate_in_all_modes(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "thermal_model": "enhanced",
                "attitude_mode": "nadir_pointing",
                "body_length_m": 0.2,
                "orbit_count": 1,
                "time_step_s": 30.0,
            }
        )
        single = run_single_mode(request)
        self.assertEqual(single.primary.request.thermal_model, "enhanced")
        self.assertEqual(single.primary.request.attitude_mode, "nadir_pointing")

        env = run_environment_comparison_mode(request)
        for curve in all_curves(env):
            self.assertEqual(curve.request.thermal_model, "enhanced")
            self.assertEqual(curve.request.attitude_mode, "nadir_pointing")
            self.assertEqual(curve.request.body_length_m, 0.2)

        base = run_baseline_comparison_mode(
            GuiRunRequest(**{**request.__dict__, "mass_kg": 8.0})
        )
        reference, modified = all_curves(base)
        self.assertEqual(reference.request.thermal_model, "legacy")
        self.assertEqual(modified.request.thermal_model, "enhanced")
        self.assertEqual(modified.request.attitude_mode, "nadir_pointing")

    def test_legacy_gui_default_preserves_v1_finals(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "thermal_model": "legacy",
                "beta_deg": 0.0,
                "orbit_count": 5,
                "time_step_s": 1.0,
            }
        )
        finals = [
            temperature_metrics_c(curve.result)["final_c"]
            for curve in all_curves(run_environment_comparison_mode(request))
        ]
        self.assertAlmostEqual(finals[0], -12.5661, places=3)
        self.assertAlmostEqual(finals[1], -6.8313, places=3)
        self.assertAlmostEqual(finals[2], -4.5386, places=3)


if __name__ == "__main__":
    unittest.main()
