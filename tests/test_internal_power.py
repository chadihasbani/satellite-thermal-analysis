"""Constant internal-power schedule tests."""

from __future__ import annotations

import unittest

from satellite_thermal.gui_support import (
    GuiRunRequest,
    all_curves,
    default_gui_request,
    power_schedule_from_request,
    run_environment_comparison_mode,
    temperature_metrics_c,
)
from satellite_thermal.internal_power import (
    ILLUSTRATIVE_NOMINAL_W,
    PowerScheduleKind,
    constant_power_schedule,
    parse_power_schedule_kind,
)


class ConstantPowerTests(unittest.TestCase):
    def test_constant_schedule_values(self) -> None:
        schedule = constant_power_schedule(5.0)
        self.assertEqual(schedule.kind, PowerScheduleKind.CONSTANT.value)
        self.assertEqual(schedule.power_w_at(0.0, False), 5.0)
        self.assertEqual(schedule.power_w_at(100.0, True), 5.0)
        self.assertEqual(schedule.state_label_at(10.0, False), "constant")
        self.assertIsNone(schedule.next_scheduled_transition_s(0.0))

    def test_parse_rejects_non_constant(self) -> None:
        with self.assertRaises(ValueError):
            parse_power_schedule_kind("periodic_high")

    def test_gui_request_builds_constant_schedule(self) -> None:
        request = default_gui_request()
        schedule = power_schedule_from_request(request)
        self.assertEqual(schedule.constant_power_w, ILLUSTRATIVE_NOMINAL_W)

    def test_v1_constant_power_baselines_unchanged(self) -> None:
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
