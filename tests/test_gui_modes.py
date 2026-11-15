"""GUI mode orchestration tests for the simplified simulator."""

from __future__ import annotations

import unittest

from satellite_thermal.gui_support import (
    ENV_CASE_A,
    ENV_CASE_B,
    ENV_CASE_C,
    GuiRunRequest,
    all_curves,
    default_gui_request,
    default_inspect_curve_name,
    run_environment_comparison_mode,
    run_single_mode,
    temperature_metrics_c,
)


def _short(**overrides) -> GuiRunRequest:
    base = default_gui_request().__dict__
    base.update({"orbit_count": 1, "time_step_s": 30.0})
    base.update(overrides)
    return GuiRunRequest(**base)


class GuiModeTests(unittest.TestCase):
    def test_single_mode_returns_one_curve(self) -> None:
        study = run_single_mode(_short())
        self.assertEqual(study.mode, "single")
        self.assertEqual(len(all_curves(study)), 1)
        self.assertEqual(default_inspect_curve_name(study), study.primary.name)

    def test_environment_comparison_three_cases(self) -> None:
        study = run_environment_comparison_mode(_short())
        curves = all_curves(study)
        self.assertEqual(study.mode, "environment_compare")
        self.assertEqual([c.name for c in curves], [ENV_CASE_A, ENV_CASE_B, ENV_CASE_C])
        self.assertFalse(curves[0].request.include_earth_infrared)
        self.assertFalse(curves[0].request.include_albedo)
        self.assertTrue(curves[1].request.include_earth_infrared)
        self.assertFalse(curves[1].request.include_albedo)
        self.assertTrue(curves[2].request.include_earth_infrared)
        self.assertTrue(curves[2].request.include_albedo)
        self.assertEqual(default_inspect_curve_name(study), ENV_CASE_C)

    def test_environment_compare_preserves_shared_spacecraft(self) -> None:
        request = _short(mass_kg=4.2, beta_deg=15.0)
        study = run_environment_comparison_mode(request)
        for curve in all_curves(study):
            self.assertAlmostEqual(curve.request.mass_kg, 4.2)
            self.assertAlmostEqual(curve.request.beta_deg, 15.0)


class LegacyBaselineTests(unittest.TestCase):
    def test_v1_environment_finals(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "orbit_count": 5,
                "time_step_s": 1.0,
                "beta_deg": 0.0,
                "thermal_model": "legacy",
            }
        )
        study = run_environment_comparison_mode(request)
        finals = [
            temperature_metrics_c(curve.result)["final_c"]
            for curve in all_curves(study)
        ]
        self.assertAlmostEqual(finals[0], -12.5661, places=3)
        self.assertAlmostEqual(finals[1], -6.8313, places=3)
        self.assertAlmostEqual(finals[2], -4.5386, places=3)


if __name__ == "__main__":
    unittest.main()
