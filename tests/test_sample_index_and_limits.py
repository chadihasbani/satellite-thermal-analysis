"""Tests for sample-index clamping and the interactive sample cap."""

from __future__ import annotations

import unittest

from satellite_thermal.gui_support import (
    GuiRunRequest,
    MAX_GUI_SAMPLES,
    clamp_sample_index,
    default_gui_request,
    estimate_gui_sample_count,
    validate_gui_request,
)
from satellite_thermal.internal_power import constant_power_schedule
from satellite_thermal.orbital_simulation import simulate_orbital_eclipse
from satellite_thermal.parameters import Phase1Parameters


class SampleIndexHelpersTests(unittest.TestCase):
    def test_clamp_sample_index_bounds(self) -> None:
        self.assertEqual(clamp_sample_index(10, -3), 0)
        self.assertEqual(clamp_sample_index(10, 0), 0)
        self.assertEqual(clamp_sample_index(10, 9), 9)
        self.assertEqual(clamp_sample_index(10, 99), 9)
        with self.assertRaises(ValueError):
            clamp_sample_index(0, 0)


class GuiSampleLimitTests(unittest.TestCase):
    def test_tiny_time_step_exceeds_interactive_cap(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "orbit_count": 1,
                "time_step_s": 0.01,
                "internal_heat_w": 5.0,
            }
        )
        estimate = estimate_gui_sample_count(request)
        self.assertGreater(estimate, MAX_GUI_SAMPLES)
        with self.assertRaises(ValueError) as ctx:
            validate_gui_request(request)
        message = str(ctx.exception)
        self.assertIn(f"{MAX_GUI_SAMPLES:,}", message)
        self.assertIn("too large", message.lower())

    def test_lowered_cap_rejects_moderate_constant_run(self) -> None:
        import satellite_thermal.gui_support as gui_support

        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "orbit_count": 1,
                "time_step_s": 60.0,
            }
        )
        original_limit = gui_support.MAX_GUI_SAMPLES
        try:
            gui_support.MAX_GUI_SAMPLES = 50
            estimate = estimate_gui_sample_count(request)
            self.assertGreater(estimate, 50)
            with self.assertRaises(ValueError) as ctx:
                validate_gui_request(request)
            self.assertIn("50", str(ctx.exception))
        finally:
            gui_support.MAX_GUI_SAMPLES = original_limit


class MaxSamplesRuntimeGuardTests(unittest.TestCase):
    def test_max_samples_raises_without_partial_result(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            simulate_orbital_eclipse(
                orbit_count=1,
                time_step_s=1.0,
                parameters=Phase1Parameters(internal_heat_w=5.0),
                power_schedule=constant_power_schedule(5.0),
                max_samples=5,
            )
        message = str(ctx.exception)
        self.assertIn("max_samples", message.lower())


if __name__ == "__main__":
    unittest.main()
