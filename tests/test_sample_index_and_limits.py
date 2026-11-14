"""Tests for irregular sample selection and GUI/runtime sample limits."""

from __future__ import annotations

import math
import unittest

from satellite_thermal.gui_support import (
    GuiRunRequest,
    MAX_GUI_SAMPLES,
    clamp_sample_index,
    count_scheduled_power_events,
    default_gui_request,
    estimate_gui_sample_count,
    power_schedule_from_request,
    run_single_mode,
    temperature_history_csv,
    validate_gui_request,
)
from satellite_thermal.heat_flows import heat_flow_at_index
from satellite_thermal.internal_power import (
    InternalPowerSchedule,
    PowerInterval,
    PowerScheduleKind,
    constant_power_schedule,
)
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


class EventAwareSampleEstimationTests(unittest.TestCase):
    def test_custom_interval_events_increase_estimate(self) -> None:
        base = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "orbit_count": 1,
                "time_step_s": 5.0,
                "power_schedule_kind": PowerScheduleKind.CONSTANT.value,
            }
        )
        pulsed = GuiRunRequest(
            **{
                **base.__dict__,
                "power_schedule_kind": PowerScheduleKind.CUSTOM_INTERVALS.value,
                "custom_intervals_text": "1,2,100; 10,11,80",
            }
        )
        base_estimate = estimate_gui_sample_count(base)
        pulsed_estimate = estimate_gui_sample_count(pulsed)
        self.assertGreaterEqual(pulsed_estimate - base_estimate, 4)
        schedule = power_schedule_from_request(pulsed)
        # Duration is one LEO period at 500 km (~5677 s); edges at 1,2,10,11.
        self.assertEqual(count_scheduled_power_events(schedule, 5676.0), 4)

    def test_dense_periodic_schedule_rejected_before_run(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "orbit_count": 1,
                "time_step_s": 5.0,
                "power_schedule_kind": PowerScheduleKind.PERIODIC_HIGH.value,
                "periodic_period_s": 0.01,
                "periodic_high_duration_s": 0.005,
            }
        )
        estimate = estimate_gui_sample_count(request)
        self.assertGreater(estimate, MAX_GUI_SAMPLES)
        with self.assertRaises(ValueError) as ctx:
            validate_gui_request(request)
        message = str(ctx.exception)
        self.assertIn("power-event", message.lower())
        self.assertIn(f"{MAX_GUI_SAMPLES:,}", message)

    def test_custom_schedule_rejected_when_events_exceed_cap(self) -> None:
        import satellite_thermal.gui_support as gui_support

        chunks = [f"{i},{i + 0.5},20" for i in range(1, 40)]
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "orbit_count": 1,
                "time_step_s": 60.0,
                "power_schedule_kind": PowerScheduleKind.CUSTOM_INTERVALS.value,
                "custom_intervals_text": ";".join(chunks),
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


class IrregularTimestampSelectionTests(unittest.TestCase):
    def test_every_stored_sample_is_index_addressable(self) -> None:
        schedule = InternalPowerSchedule(
            kind=PowerScheduleKind.CUSTOM_INTERVALS.value,
            constant_power_w=5.0,
            intervals=(PowerInterval(1.0, 2.0, 100.0, label="pulse"),),
        ).validated()
        result = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=5.0,
            parameters=Phase1Parameters(internal_heat_w=5.0),
            power_schedule=schedule,
            include_earth_infrared=True,
            include_albedo=True,
        )
        times = result.time_s
        self.assertGreater(len(times), 2)
        # Off-grid event samples exist and have unique indices.
        start_index = next(i for i, t in enumerate(times) if math.isclose(t, 1.0, abs_tol=1e-12))
        end_index = next(i for i, t in enumerate(times) if math.isclose(t, 2.0, abs_tol=1e-12))
        self.assertNotEqual(start_index, end_index)
        for index, time_s in enumerate(times):
            self.assertEqual(clamp_sample_index(len(times), index), index)
            self.assertEqual(result.time_s[index], time_s)

    def test_event_boundary_selection_matches_power_state(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "orbit_count": 1,
                "time_step_s": 5.0,
                "power_schedule_kind": PowerScheduleKind.CUSTOM_INTERVALS.value,
                "custom_intervals_text": "1,2,100",
                "internal_heat_w": 5.0,
            }
        )
        named = run_single_mode(request).primary
        schedule = power_schedule_from_request(named.request)
        times = named.result.time_s
        start_index = next(i for i, t in enumerate(times) if math.isclose(t, 1.0, abs_tol=1e-12))
        end_index = next(i for i, t in enumerate(times) if math.isclose(t, 2.0, abs_tol=1e-12))

        snap_start = heat_flow_at_index(
            named.result,
            start_index,
            named.thermal,
            named.orbit,
            named.request.include_earth_infrared,
            named.request.include_albedo,
            named.earth_infrared,
            named.albedo,
            power_schedule=schedule,
        )
        snap_end = heat_flow_at_index(
            named.result,
            end_index,
            named.thermal,
            named.orbit,
            named.request.include_earth_infrared,
            named.request.include_albedo,
            named.earth_infrared,
            named.albedo,
            power_schedule=schedule,
        )
        self.assertAlmostEqual(snap_start.time_s, 1.0, places=12)
        self.assertAlmostEqual(snap_end.time_s, 2.0, places=12)
        self.assertAlmostEqual(snap_start.q_internal_w, 100.0, places=12)
        # Half-open [1, 2): sample at t=2 uses baseline again.
        self.assertAlmostEqual(snap_end.q_internal_w, 5.0, places=12)

        # CSV row at the event index agrees with the instantaneous panel.
        csv_text = temperature_history_csv((named,))
        rows = [line for line in csv_text.strip().splitlines() if line and not line.startswith("case")]
        # Find the CSV line whose time_s matches 1.0.
        matched = None
        for line in rows:
            fields = line.split(",")
            if math.isclose(float(fields[1]), 1.0, abs_tol=1e-9):
                matched = fields
                break
        self.assertIsNotNone(matched)
        assert matched is not None
        self.assertAlmostEqual(float(matched[5]), 100.0, places=6)


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
        self.assertIn("max_samples", message)
        self.assertIn("Partial results are not returned", message)

    def test_short_periodic_schedule_hits_runtime_guard(self) -> None:
        schedule = InternalPowerSchedule(
            kind=PowerScheduleKind.PERIODIC_HIGH.value,
            base_power_w=5.0,
            high_power_w=15.0,
            period_s=0.5,
            high_duration_s=0.25,
        ).validated()
        with self.assertRaises(ValueError) as ctx:
            simulate_orbital_eclipse(
                orbit_count=1,
                time_step_s=5.0,
                parameters=Phase1Parameters(internal_heat_w=5.0),
                power_schedule=schedule,
                max_samples=50,
            )
        self.assertIn("max_samples", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
