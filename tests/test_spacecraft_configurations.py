"""Tests for Checkpoint 5 spacecraft configuration presets."""

from __future__ import annotations

import math
import unittest

from satellite_thermal.gui_support import (
    GuiRunRequest,
    all_curves,
    apply_spacecraft_configuration,
    apply_thermal_scenario,
    default_gui_request,
    run_baseline_comparison_mode,
    run_environment_comparison_mode,
    run_gui_simulation,
    run_scenario_comparison_mode,
    run_single_mode,
    temperature_metrics_c,
)
from satellite_thermal.orbit_3d import _spacecraft_meshes
from satellite_thermal.spacecraft_configurations import (
    CDS_1U_HEIGHT_M,
    CDS_1U_LENGTH_M,
    CDS_1U_MAX_MASS_KG,
    CDS_1U_WIDTH_M,
    CDS_3U_HEIGHT_M,
    CDS_3U_LENGTH_M,
    CDS_3U_MAX_MASS_KG,
    CDS_3U_WIDTH_M,
    ILLUSTRATIVE_3U_MASS_KG,
    SpacecraftConfigurationId,
    build_spacecraft_configuration,
    configuration_controls_locked,
    configuration_overlay_fields,
    derived_face_areas_m2,
    mismatched_configuration_field_names,
    sync_session_values_from_configuration,
    total_exterior_area_m2,
)
from satellite_thermal.spacecraft_geometry import FACE_NAMES, RectangularBusGeometry
from satellite_thermal.surface_heating import (
    projected_solar_area_m2,
    surface_radiative_cooling_w,
)
from satellite_thermal.thermal_scenarios import ThermalScenarioId


class CubeSatEnvelopeTests(unittest.TestCase):
    def test_cds_rev14_1_envelope_dimensions(self) -> None:
        one_u = build_spacecraft_configuration(SpacecraftConfigurationId.CUBESAT_1U)
        three_u = build_spacecraft_configuration(SpacecraftConfigurationId.CUBESAT_3U)
        self.assertEqual(one_u.body_length_m, CDS_1U_LENGTH_M)
        self.assertEqual(one_u.body_width_m, CDS_1U_WIDTH_M)
        self.assertEqual(one_u.body_height_m, CDS_1U_HEIGHT_M)
        self.assertEqual(one_u.cds_max_mass_kg, CDS_1U_MAX_MASS_KG)
        self.assertLess(one_u.mass_kg, CDS_1U_MAX_MASS_KG)

        self.assertEqual(three_u.body_length_m, CDS_3U_LENGTH_M)
        self.assertEqual(three_u.body_width_m, CDS_3U_WIDTH_M)
        self.assertEqual(three_u.body_height_m, CDS_3U_HEIGHT_M)
        self.assertEqual(three_u.cds_max_mass_kg, CDS_3U_MAX_MASS_KG)
        self.assertEqual(three_u.mass_kg, ILLUSTRATIVE_3U_MASS_KG)
        self.assertLess(three_u.mass_kg, CDS_3U_MAX_MASS_KG)

    def test_face_areas_and_normals_consistency(self) -> None:
        length, width, height = 0.100, 0.100, 0.3405
        areas = derived_face_areas_m2(length, width, height)
        self.assertAlmostEqual(areas["+x"], width * height, places=12)
        self.assertAlmostEqual(areas["-x"], width * height, places=12)
        self.assertAlmostEqual(areas["+y"], length * height, places=12)
        self.assertAlmostEqual(areas["+z"], length * width, places=12)
        self.assertAlmostEqual(
            total_exterior_area_m2(length, width, height),
            sum(areas.values()),
            places=12,
        )
        geom = RectangularBusGeometry(
            length_m=length, width_m=width, height_m=height
        ).validated()
        for name in FACE_NAMES:
            self.assertAlmostEqual(geom.face_area_m2(name), areas[name], places=12)
            normal = geom.body_normal(name)
            self.assertAlmostEqual(math.sqrt(sum(v * v for v in normal)), 1.0, places=12)

    def test_illustrative_cube_matches_v1_area_defaults(self) -> None:
        cube = build_spacecraft_configuration(SpacecraftConfigurationId.ILLUSTRATIVE_CUBE)
        self.assertAlmostEqual(cube.radiating_area_m2, 0.06, places=12)
        self.assertAlmostEqual(cube.projected_area_m2, 0.01, places=12)
        self.assertEqual(cube.thermal_model, "enhanced")

    def test_legacy_preset_keeps_fixed_areas(self) -> None:
        legacy = build_spacecraft_configuration(
            SpacecraftConfigurationId.LEGACY_SIMPLIFIED
        )
        self.assertEqual(legacy.thermal_model, "legacy")
        self.assertEqual(legacy.projected_area_m2, 0.01)
        self.assertEqual(legacy.radiating_area_m2, 0.06)


class ConfigurationApplicationTests(unittest.TestCase):
    def test_apply_preserves_orbit_and_power(self) -> None:
        base = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "altitude_km": 600.0,
                "beta_deg": 20.0,
                "power_schedule_kind": "periodic_high",
                "internal_heat_w": 7.0,
                "attitude_mode": "nadir_pointing",
            }
        )
        applied = apply_spacecraft_configuration(
            base, SpacecraftConfigurationId.CUBESAT_3U
        )
        self.assertEqual(applied.altitude_km, 600.0)
        self.assertEqual(applied.beta_deg, 20.0)
        self.assertEqual(applied.power_schedule_kind, "periodic_high")
        self.assertEqual(applied.internal_heat_w, 7.0)
        self.assertEqual(applied.attitude_mode, "nadir_pointing")
        self.assertEqual(applied.body_height_m, CDS_3U_HEIGHT_M)
        self.assertEqual(applied.thermal_model, "enhanced")

    def test_custom_is_identity(self) -> None:
        base = default_gui_request()
        self.assertEqual(
            apply_spacecraft_configuration(base, SpacecraftConfigurationId.CUSTOM),
            base,
        )

    def test_session_sync_matches_solver_overlay(self) -> None:
        for configuration in (
            SpacecraftConfigurationId.LEGACY_SIMPLIFIED,
            SpacecraftConfigurationId.ILLUSTRATIVE_CUBE,
            SpacecraftConfigurationId.CUBESAT_1U,
            SpacecraftConfigurationId.CUBESAT_3U,
        ):
            session = sync_session_values_from_configuration(configuration)
            fields = {name.removeprefix("gui_"): value for name, value in session.items()}
            self.assertEqual(
                mismatched_configuration_field_names(fields, configuration),
                (),
            )
            tampered = GuiRunRequest(
                **{
                    **default_gui_request().__dict__,
                    "mass_kg": 99.0,
                    "body_height_m": 1.0,
                }
            )
            applied = apply_spacecraft_configuration(tampered, configuration)
            expected = configuration_overlay_fields(
                build_spacecraft_configuration(configuration)
            )
            for name, value in expected.items():
                self.assertEqual(getattr(applied, name), value, name)
            self.assertIn(
                "mass_kg",
                mismatched_configuration_field_names(
                    tampered.__dict__, configuration
                ),
            )
        self.assertFalse(
            configuration_controls_locked(SpacecraftConfigurationId.CUSTOM)
        )
        self.assertTrue(
            configuration_controls_locked(SpacecraftConfigurationId.CUBESAT_3U)
        )


class GeometryThermalTests(unittest.TestCase):
    def test_enhanced_emission_uses_total_exterior_area(self) -> None:
        definition = build_spacecraft_configuration(
            SpacecraftConfigurationId.CUBESAT_3U
        )
        geom = definition.geometry()
        temperature_k = 300.0
        sigma = 5.670374419e-8
        radiated = surface_radiative_cooling_w(geom, temperature_k, sigma)
        expected = (
            definition.emissivity
            * sigma
            * definition.radiating_area_m2
            * temperature_k**4
        )
        self.assertAlmostEqual(radiated, expected, places=9)

    def test_projected_area_single_face_sun(self) -> None:
        geom = RectangularBusGeometry(
            length_m=0.1, width_m=0.1, height_m=0.3405
        ).validated()
        # Sun along +X; body axes aligned with inertial.
        area = projected_solar_area_m2(
            geom,
            body_x=(1.0, 0.0, 0.0),
            body_y=(0.0, 1.0, 0.0),
            body_z=(0.0, 0.0, 1.0),
            sun_direction_inertial=(1.0, 0.0, 0.0),
        )
        self.assertAlmostEqual(area, geom.face_area_m2("+x"), places=12)

    def test_thermal_capacitance(self) -> None:
        definition = build_spacecraft_configuration(
            SpacecraftConfigurationId.CUBESAT_3U
        )
        self.assertAlmostEqual(
            definition.thermal_capacitance_j_per_k,
            definition.mass_kg * definition.specific_heat_j_per_kg_k,
            places=12,
        )


class GuiModePropagationTests(unittest.TestCase):
    def test_all_modes_propagate_3u_geometry(self) -> None:
        request = apply_spacecraft_configuration(
            GuiRunRequest(
                **{
                    **default_gui_request().__dict__,
                    "orbit_count": 1,
                    "time_step_s": 30.0,
                }
            ),
            SpacecraftConfigurationId.CUBESAT_3U,
        )
        single = run_single_mode(request)
        baseline = run_baseline_comparison_mode(request)
        environment = run_environment_comparison_mode(request)
        scenarios = run_scenario_comparison_mode(request)
        self.assertEqual(single.primary.request.body_height_m, CDS_3U_HEIGHT_M)
        self.assertEqual(baseline.primary.request.body_height_m, CDS_3U_HEIGHT_M)
        self.assertEqual(environment.primary.request.body_height_m, CDS_3U_HEIGHT_M)
        for curve in all_curves(scenarios):
            self.assertEqual(curve.request.body_height_m, CDS_3U_HEIGHT_M)
            self.assertEqual(curve.request.mass_kg, ILLUSTRATIVE_3U_MASS_KG)

    def test_scenario_overlays_keep_shared_spacecraft(self) -> None:
        request = apply_spacecraft_configuration(
            GuiRunRequest(
                **{
                    **default_gui_request().__dict__,
                    "orbit_count": 1,
                    "time_step_s": 30.0,
                }
            ),
            SpacecraftConfigurationId.CUBESAT_3U,
        )
        hot = apply_thermal_scenario(request, ThermalScenarioId.HOT)
        cold = apply_thermal_scenario(request, ThermalScenarioId.COLD)
        self.assertEqual(hot.body_height_m, cold.body_height_m)
        self.assertEqual(hot.mass_kg, cold.mass_kg)
        self.assertNotEqual(hot.solar_flux_w_per_m2, cold.solar_flux_w_per_m2)

    def test_legacy_baselines_with_legacy_configuration(self) -> None:
        request = apply_spacecraft_configuration(
            GuiRunRequest(
                **{
                    **default_gui_request().__dict__,
                    "orbit_count": 5,
                    "time_step_s": 1.0,
                }
            ),
            SpacecraftConfigurationId.LEGACY_SIMPLIFIED,
        )
        finals = [
            temperature_metrics_c(curve.result)["final_c"]
            for curve in all_curves(run_environment_comparison_mode(request))
        ]
        self.assertAlmostEqual(finals[0], -12.5661, places=3)
        self.assertAlmostEqual(finals[1], -6.8313, places=3)
        self.assertAlmostEqual(finals[2], -4.5386, places=3)

    def test_event_aware_power_with_3u(self) -> None:
        request = apply_spacecraft_configuration(
            GuiRunRequest(
                **{
                    **default_gui_request().__dict__,
                    "orbit_count": 1,
                    "time_step_s": 5.0,
                    "power_schedule_kind": "custom_intervals",
                    "custom_intervals_text": "1,2,100",
                    "internal_heat_w": 5.0,
                }
            ),
            SpacecraftConfigurationId.CUBESAT_3U,
        )
        result = run_gui_simulation(request)
        self.assertTrue(any(math.isclose(t, 1.0, abs_tol=1e-12) for t in result.time_s))


class VisualizationProportionTests(unittest.TestCase):
    def test_3u_mesh_proportions_differ_from_cube(self) -> None:
        cube = build_spacecraft_configuration(
            SpacecraftConfigurationId.ILLUSTRATIVE_CUBE
        )
        three_u = build_spacecraft_configuration(SpacecraftConfigurationId.CUBESAT_3U)

        def visual_half_extents(
            length_m: float, width_m: float, height_m: float, scale: float = 1.0
        ) -> tuple[float, float, float]:
            # Mirrors orbit_3d._spacecraft_meshes proportion mapping.
            max_dim = max(length_m, width_m, height_m, 1e-9)
            return (
                0.55 * scale * (length_m / max_dim),
                0.55 * scale * (width_m / max_dim),
                0.55 * scale * (height_m / max_dim),
            )

        cube_h = visual_half_extents(
            cube.body_length_m, cube.body_width_m, cube.body_height_m
        )
        three_h = visual_half_extents(
            three_u.body_length_m, three_u.body_width_m, three_u.body_height_m
        )
        self.assertAlmostEqual(cube_h[0], cube_h[2], places=12)
        self.assertLess(three_h[0] / three_h[2], cube_h[0] / cube_h[2])
        # Full mesh path still runs for both shapes.
        _spacecraft_meshes(
            (0.0, 0.0, 0.0),
            0.0,
            1.0,
            body_length_m=three_u.body_length_m,
            body_width_m=three_u.body_width_m,
            body_height_m=three_u.body_height_m,
        )


class RepresentativeComparisonTests(unittest.TestCase):
    def test_cube_versus_3u_temperature_difference(self) -> None:
        base = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "orbit_count": 3,
                "time_step_s": 10.0,
                "include_earth_infrared": True,
                "include_albedo": True,
            }
        )
        cube = run_gui_simulation(
            apply_spacecraft_configuration(
                base, SpacecraftConfigurationId.ILLUSTRATIVE_CUBE
            )
        )
        three_u = run_gui_simulation(
            apply_spacecraft_configuration(
                base, SpacecraftConfigurationId.CUBESAT_3U
            )
        )
        cube_final = temperature_metrics_c(cube)["final_c"]
        three_final = temperature_metrics_c(three_u)["final_c"]
        # Larger radiating area and different mass move the 3U away from the cube.
        self.assertNotAlmostEqual(cube_final, three_final, places=2)
        three_def = build_spacecraft_configuration(SpacecraftConfigurationId.CUBESAT_3U)
        cube_def = build_spacecraft_configuration(
            SpacecraftConfigurationId.ILLUSTRATIVE_CUBE
        )
        self.assertGreater(three_def.radiating_area_m2, cube_def.radiating_area_m2)
        self.assertLess(three_def.mass_kg, cube_def.mass_kg)


if __name__ == "__main__":
    unittest.main()
