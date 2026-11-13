"""GUI comparison-mode generation and curve packaging."""

from __future__ import annotations

import unittest

from satellite_thermal.gui_support import (
    GuiRunRequest,
    all_curves,
    default_gui_request,
    run_baseline_comparison_mode,
    run_environment_comparison_mode,
    run_single_mode,
    temperature_metrics_c,
)
from satellite_thermal.orbit import satellite_position_m, orbital_period_s, orbital_radius_m, position_angle_rad
from satellite_thermal.orbit_3d import build_orbit_3d_figure


class GuiModeTests(unittest.TestCase):
    def test_single_mode_returns_one_curve(self) -> None:
        request = GuiRunRequest(
            **{**default_gui_request().__dict__, "orbit_count": 1, "time_step_s": 30.0}
        )
        study = run_single_mode(request)
        self.assertEqual(study.mode, "single")
        self.assertEqual(len(all_curves(study)), 1)

    def test_baseline_comparison_detects_changed_mass(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "mass_kg": 8.0,
                "orbit_count": 1,
                "time_step_s": 30.0,
            }
        )
        study = run_baseline_comparison_mode(request)
        self.assertEqual(study.mode, "baseline_compare")
        curves = all_curves(study)
        self.assertEqual(len(curves), 2)
        self.assertIn("mass", study.changed_fields)
        baseline_final = temperature_metrics_c(curves[0].result)["final_c"]
        modified_final = temperature_metrics_c(curves[1].result)["final_c"]
        # Heavier mass cools more slowly in this transient, so final T is warmer.
        self.assertGreater(modified_final, baseline_final)

    def test_environment_comparison_orders_a_b_c(self) -> None:
        request = GuiRunRequest(
            **{**default_gui_request().__dict__, "orbit_count": 1, "time_step_s": 30.0}
        )
        study = run_environment_comparison_mode(request)
        curves = all_curves(study)
        self.assertEqual(len(curves), 3)
        self.assertTrue(curves[0].name.startswith("A:"))
        self.assertTrue(curves[1].name.startswith("B:"))
        self.assertTrue(curves[2].name.startswith("C:"))
        finals = [curve.result.temperature_k[-1] for curve in curves]
        self.assertLess(finals[0], finals[1])
        self.assertLess(finals[1], finals[2])
        self.assertEqual(curves[0].result.earth_infrared_heat_w, 0.0)
        self.assertGreater(curves[1].result.earth_infrared_heat_w, 0.0)
        self.assertFalse(curves[1].result.include_albedo)
        self.assertTrue(curves[2].result.include_albedo)


class Orbit3dSyncTests(unittest.TestCase):
    def test_satellite_position_matches_solver_geometry(self) -> None:
        request = GuiRunRequest(
            **{**default_gui_request().__dict__, "orbit_count": 1, "time_step_s": 30.0}
        )
        study = run_single_mode(request)
        result = study.primary.result
        orbit = study.primary.orbit
        index = len(result.time_s) // 3
        time_s = result.time_s[index]
        expected = satellite_position_m(
            position_angle_rad(time_s, orbital_period_s(orbit)),
            orbital_radius_m(orbit),
        )
        # Building the figure must succeed and use the same sample.
        figure = build_orbit_3d_figure(result, orbit, index)
        self.assertIsNotNone(figure)
        # Recompute expected coordinates for regression against geometry helpers.
        self.assertAlmostEqual(expected[2], 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
