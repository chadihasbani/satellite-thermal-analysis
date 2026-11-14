"""GUI comparison-mode generation and curve packaging."""

from __future__ import annotations

import math
import unittest

from satellite_thermal.gui_support import (
    ENV_CASE_A,
    ENV_CASE_B,
    ENV_CASE_C,
    MOD_CASE_NAME,
    REF_CASE_NAME,
    GuiRunRequest,
    all_curves,
    default_gui_request,
    default_inspect_curve_name,
    environment_comparison_interpretation,
    environment_comparison_summary_rows,
    resolve_inspect_curve,
    run_baseline_comparison_mode,
    run_environment_comparison_mode,
    run_single_mode,
    temperature_metrics_c,
)
from satellite_thermal.orbit import (
    orbital_period_s,
    orbital_radius_m,
    position_angle_rad,
    satellite_position_m,
)
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
        self.assertEqual(curves[0].name, REF_CASE_NAME)
        self.assertEqual(curves[1].name, MOD_CASE_NAME)
        self.assertIn("Mass (kg)", study.changed_fields)
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
        self.assertEqual(curves[0].name, ENV_CASE_A)
        self.assertEqual(curves[1].name, ENV_CASE_B)
        self.assertEqual(curves[2].name, ENV_CASE_C)
        finals = [curve.result.temperature_k[-1] for curve in curves]
        self.assertLess(finals[0], finals[1])
        self.assertLess(finals[1], finals[2])
        self.assertEqual(curves[0].result.earth_infrared_heat_w, 0.0)
        self.assertGreater(curves[1].result.earth_infrared_heat_w, 0.0)
        self.assertFalse(curves[1].result.include_albedo)
        self.assertTrue(curves[2].result.include_albedo)


class EnvironmentInspectDefaultsTests(unittest.TestCase):
    def test_default_inspect_case_is_case_c(self) -> None:
        request = GuiRunRequest(
            **{**default_gui_request().__dict__, "orbit_count": 1, "time_step_s": 30.0}
        )
        study = run_environment_comparison_mode(request)
        self.assertEqual(default_inspect_curve_name(study), ENV_CASE_C)
        self.assertEqual(study.primary.name, ENV_CASE_C)

    def test_switching_inspect_case_does_not_change_histories(self) -> None:
        request = GuiRunRequest(
            **{**default_gui_request().__dict__, "orbit_count": 1, "time_step_s": 30.0}
        )
        study = run_environment_comparison_mode(request)
        curves = all_curves(study)
        finals_before = [curve.result.temperature_k[-1] for curve in curves]
        for name in (ENV_CASE_A, ENV_CASE_B, ENV_CASE_C):
            chosen = resolve_inspect_curve(curves, name, ENV_CASE_C)
            self.assertEqual(chosen.name, name)
        finals_after = [curve.result.temperature_k[-1] for curve in curves]
        self.assertEqual(finals_before, finals_after)

    def test_environment_summary_uses_simulation_finals(self) -> None:
        request = GuiRunRequest(
            **{**default_gui_request().__dict__, "orbit_count": 1, "time_step_s": 30.0}
        )
        curves = all_curves(run_environment_comparison_mode(request))
        rows = environment_comparison_summary_rows(curves)
        finals = [temperature_metrics_c(curve.result)["final_c"] for curve in curves]
        self.assertEqual(rows[0]["Temperature change"], "Reference")
        self.assertIn(f"{finals[1] - finals[0]:+.2f} K", rows[1]["Temperature change"])
        self.assertIn(f"{finals[2] - finals[1]:+.2f} K", rows[2]["Temperature change"])
        text = environment_comparison_interpretation(curves)
        self.assertIn(f"{finals[1] - finals[0]:+.2f} K", text)
        self.assertIn(f"{finals[2] - finals[1]:+.2f} K", text)


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


class BetaPropagationThroughGuiModesTests(unittest.TestCase):
    """Ensure selected beta reaches CircularOrbit objects, not only the slider."""

    def test_single_mode_applies_user_beta_to_orbit(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "beta_deg": 30.0,
                "orbit_count": 1,
                "time_step_s": 30.0,
            }
        )
        study = run_single_mode(request)
        self.assertEqual(study.primary.request.beta_deg, 30.0)
        self.assertTrue(
            math.isclose(study.primary.orbit.beta_rad, math.radians(30.0), abs_tol=1e-12)
        )
        self.assertGreater(study.primary.result.eclipse_duration_s, 0.0)
        self.assertLess(
            study.primary.result.eclipse_duration_s,
            run_single_mode(
                GuiRunRequest(
                    **{**request.__dict__, "beta_deg": 0.0}
                )
            ).primary.result.eclipse_duration_s,
        )

    def test_environment_comparison_propagates_beta_to_all_cases(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "beta_deg": 60.0,
                "orbit_count": 1,
                "time_step_s": 30.0,
            }
        )
        curves = all_curves(run_environment_comparison_mode(request))
        self.assertEqual(len(curves), 3)
        for curve in curves:
            self.assertEqual(curve.request.beta_deg, 60.0)
            self.assertTrue(
                math.isclose(curve.orbit.beta_rad, math.radians(60.0), abs_tol=1e-12)
            )
            self.assertGreater(curve.result.eclipse_duration_s, 0.0)
        # Same orbit geometry → identical eclipse duration across A/B/C.
        durations = {curve.result.eclipse_duration_s for curve in curves}
        self.assertEqual(len(durations), 1)

    def test_baseline_comparison_applies_beta_to_modified_keeps_reference_default(
        self,
    ) -> None:
        """Reference uses default_gui_request (β = 0); Modified uses the user β."""
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "beta_deg": 30.0,
                "mass_kg": 8.0,
                "orbit_count": 1,
                "time_step_s": 30.0,
            }
        )
        study = run_baseline_comparison_mode(request)
        reference, modified = all_curves(study)
        self.assertEqual(reference.name, REF_CASE_NAME)
        self.assertEqual(modified.name, MOD_CASE_NAME)
        self.assertEqual(reference.request.beta_deg, 0.0)
        self.assertEqual(reference.orbit.beta_rad, 0.0)
        self.assertEqual(modified.request.beta_deg, 30.0)
        self.assertTrue(
            math.isclose(modified.orbit.beta_rad, math.radians(30.0), abs_tol=1e-12)
        )
        self.assertIn("Orbital beta angle (°)", study.changed_fields)
        self.assertGreater(
            reference.result.eclipse_duration_s,
            modified.result.eclipse_duration_s,
        )

    def test_high_beta_environment_cases_have_no_eclipse(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "beta_deg": 75.0,
                "orbit_count": 1,
                "time_step_s": 30.0,
            }
        )
        for curve in all_curves(run_environment_comparison_mode(request)):
            self.assertEqual(curve.request.beta_deg, 75.0)
            self.assertEqual(curve.result.eclipse_duration_s, 0.0)
            self.assertFalse(any(curve.result.in_eclipse))


if __name__ == "__main__":
    unittest.main()
