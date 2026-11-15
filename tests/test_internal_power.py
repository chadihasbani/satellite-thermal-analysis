"""Independent verification of time-dependent internal power schedules."""

from __future__ import annotations

import math
import unittest

from satellite_thermal.gui_support import (
    GuiRunRequest,
    all_curves,
    default_gui_request,
    power_schedule_from_request,
    run_baseline_comparison_mode,
    run_environment_comparison_mode,
    run_single_mode,
    temperature_history_csv,
    temperature_metrics_c,
)
from satellite_thermal.heat_flows import heat_flow_at_index
from satellite_thermal.internal_power import (
    InternalPowerSchedule,
    PowerInterval,
    PowerScheduleKind,
    constant_power_schedule,
)
from satellite_thermal.orbit import CircularOrbit, in_eclipse_at_time, orbital_period_s
from satellite_thermal.orbital_simulation import simulate_orbital_eclipse
from satellite_thermal.parameters import Phase1Parameters


class ConstantAndZeroPowerTests(unittest.TestCase):
    def test_constant_schedule_matches_phase1_field(self) -> None:
        schedule = constant_power_schedule(5.0)
        self.assertEqual(schedule.power_w_at(0.0, False), 5.0)
        self.assertEqual(schedule.power_w_at(1000.0, True), 5.0)
        self.assertEqual(schedule.state_label_at(0.0, False), "constant")

    def test_zero_internal_power(self) -> None:
        schedule = constant_power_schedule(0.0)
        self.assertEqual(schedule.power_w_at(10.0, False), 0.0)
        thermal = Phase1Parameters(internal_heat_w=0.0)
        result = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=30.0,
            parameters=thermal,
            power_schedule=schedule,
        )
        self.assertTrue(math.isfinite(result.temperature_k[-1]))

    def test_constant_power_reproduces_legacy_without_schedule_arg(self) -> None:
        thermal = Phase1Parameters()
        orbit = CircularOrbit()
        with_default = simulate_orbital_eclipse(
            orbit_count=2, time_step_s=10.0, parameters=thermal, orbit=orbit
        )
        with_explicit = simulate_orbital_eclipse(
            orbit_count=2,
            time_step_s=10.0,
            parameters=thermal,
            orbit=orbit,
            power_schedule=constant_power_schedule(thermal.internal_heat_w),
        )
        for left, right in zip(with_default.temperature_k, with_explicit.temperature_k):
            self.assertTrue(math.isclose(left, right, abs_tol=1e-12))


class PeriodicAndEclipseScheduleTests(unittest.TestCase):
    def test_periodic_switching_half_open_intervals(self) -> None:
        schedule = InternalPowerSchedule(
            kind=PowerScheduleKind.PERIODIC_HIGH.value,
            base_power_w=5.0,
            high_power_w=15.0,
            period_s=100.0,
            high_duration_s=20.0,
        ).validated()
        self.assertEqual(schedule.power_w_at(0.0, False), 15.0)
        self.assertEqual(schedule.power_w_at(19.999, False), 15.0)
        self.assertEqual(schedule.power_w_at(20.0, False), 5.0)
        self.assertEqual(schedule.power_w_at(100.0, False), 15.0)
        self.assertEqual(schedule.state_label_at(5.0, False), "periodic_high")
        self.assertEqual(schedule.state_label_at(50.0, False), "periodic_base")

    def test_eclipse_reduced_uses_actual_eclipse_flag(self) -> None:
        schedule = InternalPowerSchedule(
            kind=PowerScheduleKind.ECLIPSE_REDUCED.value,
            sunlight_power_w=5.0,
            eclipse_power_w=1.0,
        ).validated()
        orbit = CircularOrbit(beta_rad=0.0)
        period = orbital_period_s(orbit)
        sunlit_t = 0.0
        eclipse_t = 0.5 * period
        self.assertFalse(in_eclipse_at_time(sunlit_t, orbit))
        self.assertTrue(in_eclipse_at_time(eclipse_t, orbit))
        self.assertEqual(
            schedule.power_w_at(sunlit_t, in_eclipse_at_time(sunlit_t, orbit)),
            5.0,
        )
        self.assertEqual(
            schedule.power_w_at(eclipse_t, in_eclipse_at_time(eclipse_t, orbit)),
            1.0,
        )

        # High beta: continuous sunlight → always sunlight power.
        high_beta = CircularOrbit(beta_rad=math.radians(75.0))
        mid = 0.5 * orbital_period_s(high_beta)
        self.assertFalse(in_eclipse_at_time(mid, high_beta))
        result = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=60.0,
            orbit=high_beta,
            power_schedule=schedule,
        )
        # Sample heat flow via schedule at stored eclipse flags.
        for time_s, flag in zip(result.time_s, result.in_eclipse):
            self.assertEqual(schedule.power_w_at(time_s, flag), 5.0)


class CustomIntervalTests(unittest.TestCase):
    def test_schedule_boundaries_and_baseline(self) -> None:
        schedule = InternalPowerSchedule(
            kind=PowerScheduleKind.CUSTOM_INTERVALS.value,
            constant_power_w=5.0,
            intervals=(
                PowerInterval(0.0, 10.0, 15.0, label="burst"),
                PowerInterval(10.0, 20.0, 1.0, label="cool"),
            ),
        ).validated()
        self.assertEqual(schedule.power_w_at(0.0, False), 15.0)
        self.assertEqual(schedule.power_w_at(9.999, False), 15.0)
        self.assertEqual(schedule.power_w_at(10.0, False), 1.0)
        self.assertEqual(schedule.power_w_at(20.0, False), 5.0)
        self.assertEqual(schedule.state_label_at(5.0, False), "burst")
        self.assertEqual(schedule.state_label_at(25.0, False), "baseline")

    def test_rejects_overlapping_and_invalid_intervals(self) -> None:
        with self.assertRaises(ValueError):
            InternalPowerSchedule(
                kind=PowerScheduleKind.CUSTOM_INTERVALS.value,
                intervals=(
                    PowerInterval(0.0, 10.0, 5.0),
                    PowerInterval(5.0, 15.0, 8.0),
                ),
            ).validated()
        with self.assertRaises(ValueError):
            PowerInterval(10.0, 10.0, 5.0).validated()
        with self.assertRaises(ValueError):
            InternalPowerSchedule(
                kind=PowerScheduleKind.PERIODIC_HIGH.value,
                period_s=100.0,
                high_duration_s=150.0,
            ).validated()


class EventAwareSteppingTests(unittest.TestCase):
    def test_off_grid_pulse_not_missed_with_coarse_dt(self) -> None:
        """5 W baseline + 100 W on [1, 2) must be seen even when dt = 5 s."""
        schedule = InternalPowerSchedule(
            kind=PowerScheduleKind.CUSTOM_INTERVALS.value,
            constant_power_w=5.0,
            intervals=(PowerInterval(1.0, 2.0, 100.0, label="pulse"),),
        ).validated()
        baseline = constant_power_schedule(5.0)
        thermal = Phase1Parameters(internal_heat_w=5.0)
        coarse_pulse = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=5.0,
            parameters=thermal,
            power_schedule=schedule,
            include_earth_infrared=True,
            include_albedo=True,
        )
        coarse_base = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=5.0,
            parameters=thermal,
            power_schedule=baseline,
            include_earth_infrared=True,
            include_albedo=True,
        )
        fine_pulse = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=0.5,
            parameters=thermal,
            power_schedule=schedule,
            include_earth_infrared=True,
            include_albedo=True,
        )
        fine_base = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=0.5,
            parameters=thermal,
            power_schedule=baseline,
            include_earth_infrared=True,
            include_albedo=True,
        )

        # Coarse run must place samples on the pulse boundaries.
        self.assertTrue(any(math.isclose(t, 1.0, abs_tol=1e-12) for t in coarse_pulse.time_s))
        self.assertTrue(any(math.isclose(t, 2.0, abs_tol=1e-12) for t in coarse_pulse.time_s))

        # Independent energy accounting on the coarse grid: extra 95 J.
        extra_energy = 0.0
        for index in range(len(coarse_pulse.time_s) - 1):
            t0 = coarse_pulse.time_s[index]
            dt = coarse_pulse.time_s[index + 1] - t0
            q = schedule.power_w_at(t0, coarse_pulse.in_eclipse[index])
            extra_energy += (q - 5.0) * dt
        self.assertAlmostEqual(extra_energy, 95.0, places=9)

        delta_coarse = coarse_pulse.temperature_k[-1] - coarse_base.temperature_k[-1]
        delta_fine = fine_pulse.temperature_k[-1] - fine_base.temperature_k[-1]
        self.assertGreater(delta_coarse, 0.0)
        self.assertTrue(math.isclose(delta_coarse, delta_fine, rel_tol=0.0, abs_tol=5e-4))
        # Independent first-order impulse scale: 95 J / (m cp) ≈ 0.0211 K.
        impulse_k = 95.0 / (thermal.mass_kg * thermal.specific_heat_j_per_kg_k)
        self.assertTrue(math.isclose(delta_coarse, impulse_k, rel_tol=0.0, abs_tol=0.01))

    def test_periodic_wraparound_and_zero_duration_high(self) -> None:
        wrap = InternalPowerSchedule(
            kind=PowerScheduleKind.PERIODIC_HIGH.value,
            base_power_w=5.0,
            high_power_w=20.0,
            period_s=100.0,
            high_duration_s=25.0,
        ).validated()
        self.assertEqual(wrap.next_scheduled_transition_s(0.0), 25.0)
        self.assertEqual(wrap.next_scheduled_transition_s(25.0), 100.0)
        self.assertEqual(wrap.next_scheduled_transition_s(99.0), 100.0)
        self.assertEqual(wrap.next_scheduled_transition_s(100.0), 125.0)

        always_base = InternalPowerSchedule(
            kind=PowerScheduleKind.PERIODIC_HIGH.value,
            period_s=100.0,
            high_duration_s=0.0,
            base_power_w=5.0,
            high_power_w=20.0,
        ).validated()
        self.assertIsNone(always_base.next_scheduled_transition_s(0.0))
        self.assertEqual(always_base.power_w_at(10.0, False), 5.0)

        always_high = InternalPowerSchedule(
            kind=PowerScheduleKind.PERIODIC_HIGH.value,
            period_s=100.0,
            high_duration_s=100.0,
            base_power_w=5.0,
            high_power_w=20.0,
        ).validated()
        self.assertIsNone(always_high.next_scheduled_transition_s(0.0))
        self.assertEqual(always_high.power_w_at(10.0, False), 20.0)

    def test_adjacent_custom_intervals_and_endpoint_transition(self) -> None:
        schedule = InternalPowerSchedule(
            kind=PowerScheduleKind.CUSTOM_INTERVALS.value,
            constant_power_w=5.0,
            intervals=(
                PowerInterval(0.0, 10.0, 8.0, label="a"),
                PowerInterval(10.0, 20.0, 12.0, label="b"),
            ),
        ).validated()
        self.assertEqual(schedule.next_scheduled_transition_s(0.0), 10.0)
        self.assertEqual(schedule.next_scheduled_transition_s(10.0), 20.0)
        self.assertIsNone(schedule.next_scheduled_transition_s(20.0))

        # Transition exactly at the simulation end is landed on without looping.
        result = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=30.0,
            parameters=Phase1Parameters(),
            power_schedule=InternalPowerSchedule(
                kind=PowerScheduleKind.CUSTOM_INTERVALS.value,
                constant_power_w=5.0,
                intervals=(
                    PowerInterval(
                        0.0,
                        orbital_period_s(CircularOrbit()),
                        7.0,
                        label="full",
                    ),
                ),
            ).validated(),
        )
        self.assertTrue(
            math.isclose(result.time_s[-1], result.period_s, abs_tol=1e-9)
        )
        self.assertGreater(len(result.time_s), 2)

    def test_constant_and_eclipse_reduced_report_no_schedule_events(self) -> None:
        self.assertIsNone(constant_power_schedule(5.0).next_scheduled_transition_s(1.0))
        eclipse = InternalPowerSchedule(
            kind=PowerScheduleKind.ECLIPSE_REDUCED.value,
            sunlight_power_w=5.0,
            eclipse_power_w=1.0,
        ).validated()
        self.assertIsNone(eclipse.next_scheduled_transition_s(100.0))


class ThermalResponseAndConvergenceTests(unittest.TestCase):
    def test_thermal_response_to_power_increase(self) -> None:
        cold = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=20.0,
            parameters=Phase1Parameters(internal_heat_w=0.0),
            power_schedule=constant_power_schedule(0.0),
            include_earth_infrared=False,
            include_albedo=False,
        )
        hot = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=20.0,
            parameters=Phase1Parameters(internal_heat_w=20.0),
            power_schedule=constant_power_schedule(20.0),
            include_earth_infrared=False,
            include_albedo=False,
        )
        self.assertGreater(hot.temperature_k[-1], cold.temperature_k[-1])

    def test_finer_step_near_periodic_switch_converges(self) -> None:
        schedule = InternalPowerSchedule(
            kind=PowerScheduleKind.PERIODIC_HIGH.value,
            base_power_w=5.0,
            high_power_w=20.0,
            period_s=300.0,
            high_duration_s=60.0,
        ).validated()
        coarse = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=30.0,
            power_schedule=schedule,
            include_earth_infrared=True,
            include_albedo=True,
        )
        fine = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=5.0,
            power_schedule=schedule,
            include_earth_infrared=True,
            include_albedo=True,
        )
        # Explicit Euler holds Q_internal over the open step; finer sampling
        # should stay close without requiring event-aware stepping for this case.
        self.assertTrue(
            math.isclose(
                coarse.temperature_k[-1],
                fine.temperature_k[-1],
                rel_tol=0.0,
                abs_tol=0.5,
            )
        )


class GuiPropagationAndHeatFlowTests(unittest.TestCase):
    def test_gui_modes_propagate_power_schedule(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "power_schedule_kind": "eclipse_reduced",
                "standby_power_w": 1.0,
                "nominal_power_w": 5.0,
                "orbit_count": 1,
                "time_step_s": 30.0,
            }
        )
        single = run_single_mode(request)
        self.assertEqual(single.primary.request.power_schedule_kind, "eclipse_reduced")
        schedule = power_schedule_from_request(single.primary.request)
        self.assertEqual(schedule.kind, "eclipse_reduced")

        for curve in all_curves(run_environment_comparison_mode(request)):
            self.assertEqual(curve.request.power_schedule_kind, "eclipse_reduced")

        base = run_baseline_comparison_mode(
            GuiRunRequest(**{**request.__dict__, "mass_kg": 8.0})
        )
        reference, modified = all_curves(base)
        self.assertEqual(reference.request.power_schedule_kind, "constant")
        self.assertEqual(modified.request.power_schedule_kind, "eclipse_reduced")

    def test_heat_flow_matches_schedule_and_energy_balance(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "power_schedule_kind": "periodic_high",
                "periodic_period_s": 200.0,
                "periodic_high_duration_s": 50.0,
                "nominal_power_w": 5.0,
                "high_power_w": 15.0,
                "orbit_count": 1,
                "time_step_s": 10.0,
            }
        )
        named = run_single_mode(request).primary
        schedule = power_schedule_from_request(named.request)
        for index in (0, len(named.result.time_s) // 3, len(named.result.time_s) // 2):
            snap = heat_flow_at_index(
                named.result,
                index,
                named.thermal,
                named.orbit,
                named.request.include_earth_infrared,
                named.request.include_albedo,
                named.earth_infrared,
                named.albedo,
                power_schedule=schedule,
            )
            expected = schedule.power_w_at(snap.time_s, snap.in_eclipse)
            self.assertEqual(snap.q_internal_w, expected)
            self.assertAlmostEqual(
                snap.q_net_w,
                snap.q_solar_w
                + snap.q_earth_ir_w
                + snap.q_albedo_w
                + snap.q_internal_w
                - snap.q_radiated_w,
                places=12,
            )

    def test_csv_includes_internal_power_columns(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "orbit_count": 1,
                "time_step_s": 60.0,
            }
        )
        csv_text = temperature_history_csv(all_curves(run_single_mode(request)))
        self.assertIn("q_internal_w", csv_text)
        self.assertIn("internal_power_state", csv_text)

    def test_v1_constant_power_baselines_unchanged(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "power_schedule_kind": "constant",
                "internal_heat_w": 5.0,
                "beta_deg": 0.0,
                "thermal_model": "legacy",
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
