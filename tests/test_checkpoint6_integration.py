"""Checkpoint 6 integrated verification across all five V2 upgrades.

These tests combine beta, attitude, power schedules, screening scenarios, and
CubeSat-inspired geometry. They also check discrete Euler energy accounting
and independent orbital/geometry relations. Passing them demonstrates
numerical consistency of the educational model — not flight validation.
"""

from __future__ import annotations

import math
import unittest

from satellite_thermal.attitude import AttitudeMode, body_axes_inertial
from satellite_thermal.gui_support import (
    GuiRunRequest,
    all_curves,
    apply_spacecraft_configuration,
    build_model_inputs,
    default_gui_request,
    geometry_from_request,
    power_schedule_from_request,
    run_environment_comparison_mode,
    run_gui_simulation,
    run_scenario_comparison_mode,
    run_single_mode,
    temperature_history_csv,
    temperature_metrics_c,
)
from satellite_thermal.heat_flows import heat_flow_at_index
from satellite_thermal.internal_power import PowerScheduleKind
from satellite_thermal.orbit import (
    EARTH_RADIUS_M,
    GRAVITATIONAL_PARAMETER_M3_PER_S2,
    CircularOrbit,
    analytical_eclipse_duration_s,
    critical_beta_rad,
    orbital_period_s,
    sun_direction,
)
from satellite_thermal.spacecraft_configurations import (
    CDS_3U_HEIGHT_M,
    SpacecraftConfigurationId,
    derived_face_areas_m2,
    total_exterior_area_m2,
)
from satellite_thermal.spacecraft_geometry import FACE_NAMES, RectangularBusGeometry
from satellite_thermal.surface_heating import projected_solar_area_m2
from satellite_thermal.thermal_scenarios import (
    SCENARIO_CASE_COLD,
    SCENARIO_CASE_HOT,
    SCENARIO_CASE_NOMINAL,
    ThermalScenarioId,
)


def _base_3u_request(**overrides: object) -> GuiRunRequest:
    request = apply_spacecraft_configuration(
        default_gui_request(),
        SpacecraftConfigurationId.CUBESAT_3U,
    )
    values = {
        **request.__dict__,
        "orbit_count": 3,
        "time_step_s": 5.0,
        "altitude_km": 500.0,
        "beta_deg": 0.0,
        "attitude_mode": AttitudeMode.NADIR_POINTING.value,
        "power_schedule_kind": PowerScheduleKind.CONSTANT.value,
        "internal_heat_w": 5.0,
        "include_earth_infrared": True,
        "include_albedo": True,
        **overrides,
    }
    return GuiRunRequest(**values)


def _discrete_energy_residual_j(
    request: GuiRunRequest,
    result,
) -> float:
    """Σ Q_net Δt − m cp ΔT using Euler step-start heat flows."""
    thermal, orbit, earth_ir, albedo = build_model_inputs(request)
    schedule = power_schedule_from_request(request)
    geometry = geometry_from_request(request)
    capacitance = thermal.mass_kg * thermal.specific_heat_j_per_kg_k
    integrated = 0.0
    for index in range(len(result.time_s) - 1):
        snap = heat_flow_at_index(
            result,
            index,
            thermal,
            orbit,
            request.include_earth_infrared,
            request.include_albedo,
            earth_ir,
            albedo,
            thermal_model=request.thermal_model,
            geometry=geometry,
            attitude_mode=request.attitude_mode,
            power_schedule=schedule,
        )
        dt = result.time_s[index + 1] - result.time_s[index]
        integrated += snap.q_net_w * dt
    stored = capacitance * (result.temperature_k[-1] - result.temperature_k[0])
    return integrated - stored


def _independent_period_s(altitude_m: float) -> float:
    radius = EARTH_RADIUS_M + altitude_m
    return 2.0 * math.pi * math.sqrt(radius**3 / GRAVITATIONAL_PARAMETER_M3_PER_S2)


def _independent_critical_beta_rad(altitude_m: float) -> float:
    radius = EARTH_RADIUS_M + altitude_m
    return math.asin(EARTH_RADIUS_M / radius)


class Checkpoint6IntegratedCases(unittest.TestCase):
    def test_case_a_generic_3u_nominal(self) -> None:
        request = _base_3u_request()
        result = run_gui_simulation(request)
        metrics = temperature_metrics_c(result)
        period = orbital_period_s(
            CircularOrbit(altitude_m=500_000.0, beta_rad=0.0).validated()
        )
        eclipse = analytical_eclipse_duration_s(
            CircularOrbit(altitude_m=500_000.0, beta_rad=0.0).validated()
        )
        self.assertAlmostEqual(result.period_s, period, places=6)
        # Stored eclipse_duration_s is step-sampled; analytical is continuous.
        self.assertGreater(eclipse, 0.0)
        self.assertLess(
            abs(result.eclipse_duration_s - eclipse),
            request.time_step_s + 1e-9,
        )
        self.assertTrue(any(result.in_eclipse))
        self.assertEqual(request.body_height_m, CDS_3U_HEIGHT_M)
        self.assertEqual(request.attitude_mode, "nadir_pointing")
        self.assertAlmostEqual(metrics["initial_c"], 20.0, places=8)
        # Sanity: temperatures remain finite and physically ordered for this case.
        self.assertTrue(math.isfinite(metrics["final_c"]))
        self.assertLessEqual(metrics["minimum_c"], metrics["maximum_c"])

    def test_case_b_high_beta_no_eclipse_warmer_than_beta0(self) -> None:
        low = run_gui_simulation(_base_3u_request(beta_deg=0.0))
        high = run_gui_simulation(_base_3u_request(beta_deg=75.0))
        beta_c_deg = math.degrees(_independent_critical_beta_rad(500_000.0))
        self.assertGreater(75.0, beta_c_deg)
        self.assertEqual(high.eclipse_duration_s, 0.0)
        self.assertFalse(any(high.in_eclipse))
        self.assertGreater(low.eclipse_duration_s, 0.0)
        # Continuous sunlight should leave the craft warmer by end of run.
        self.assertGreater(
            temperature_metrics_c(high)["final_c"],
            temperature_metrics_c(low)["final_c"],
        )

    def test_case_c_off_grid_power_event_aware(self) -> None:
        request = _base_3u_request(
            power_schedule_kind=PowerScheduleKind.CUSTOM_INTERVALS.value,
            custom_intervals_text="1,2,100",
            internal_heat_w=5.0,
            time_step_s=5.0,
            orbit_count=1,
        )
        result = run_gui_simulation(request)
        self.assertTrue(any(math.isclose(t, 1.0, abs_tol=1e-12) for t in result.time_s))
        self.assertTrue(any(math.isclose(t, 2.0, abs_tol=1e-12) for t in result.time_s))
        schedule = power_schedule_from_request(request)
        extra = 0.0
        for index in range(len(result.time_s) - 1):
            t0 = result.time_s[index]
            dt = result.time_s[index + 1] - t0
            q = schedule.power_w_at(t0, result.in_eclipse[index])
            extra += (q - 5.0) * dt
        self.assertAlmostEqual(extra, 95.0, places=9)

    def test_case_d_attitude_comparison(self) -> None:
        finals = {}
        for attitude in (
            AttitudeMode.FIXED_INERTIAL.value,
            AttitudeMode.NADIR_POINTING.value,
            AttitudeMode.SUN_POINTING.value,
        ):
            result = run_gui_simulation(_base_3u_request(attitude_mode=attitude))
            finals[attitude] = temperature_metrics_c(result)["final_c"]
        # Different prescribed attitudes must not collapse to identical histories
        # for a non-cubic 3U bus under the same environment.
        unique = {round(value, 4) for value in finals.values()}
        self.assertGreaterEqual(len(unique), 2)

    def test_case_e_screening_scenarios_same_spacecraft(self) -> None:
        request = _base_3u_request(orbit_count=2, time_step_s=10.0)
        study = run_scenario_comparison_mode(request)
        curves = all_curves(study)
        by_name = {curve.name: curve for curve in curves}
        self.assertEqual(set(by_name), {SCENARIO_CASE_COLD, SCENARIO_CASE_NOMINAL, SCENARIO_CASE_HOT})
        for curve in curves:
            self.assertEqual(curve.request.body_height_m, CDS_3U_HEIGHT_M)
            self.assertEqual(curve.request.mass_kg, request.mass_kg)
        cold = temperature_metrics_c(by_name[SCENARIO_CASE_COLD].result)["final_c"]
        nominal = temperature_metrics_c(by_name[SCENARIO_CASE_NOMINAL].result)["final_c"]
        hot = temperature_metrics_c(by_name[SCENARIO_CASE_HOT].result)["final_c"]
        self.assertLess(cold, nominal)
        self.assertLess(nominal, hot)


class Checkpoint6EnergyBalance(unittest.TestCase):
    def test_discrete_euler_energy_identity(self) -> None:
        request = _base_3u_request(orbit_count=2, time_step_s=5.0)
        result = run_gui_simulation(request)
        residual = _discrete_energy_residual_j(request, result)
        capacitance = request.mass_kg * request.specific_heat_j_per_kg_k
        # Relative to characteristic stored-energy scale.
        scale = max(1.0, abs(capacitance * (result.temperature_k[-1] - result.temperature_k[0])))
        self.assertLess(abs(residual) / scale, 1e-9)

    def test_eclipse_zeros_solar_and_albedo_instantaneous(self) -> None:
        request = _base_3u_request(orbit_count=1, time_step_s=10.0)
        result = run_gui_simulation(request)
        thermal, orbit, earth_ir, albedo = build_model_inputs(request)
        eclipse_index = next(i for i, flag in enumerate(result.in_eclipse) if flag)
        snap = heat_flow_at_index(
            result,
            eclipse_index,
            thermal,
            orbit,
            True,
            True,
            earth_ir,
            albedo,
            thermal_model=request.thermal_model,
            geometry=geometry_from_request(request),
            attitude_mode=request.attitude_mode,
            power_schedule=power_schedule_from_request(request),
        )
        self.assertAlmostEqual(snap.q_solar_w, 0.0, places=12)
        self.assertAlmostEqual(snap.q_albedo_w, 0.0, places=12)
        self.assertGreater(snap.q_earth_ir_w, 0.0)
        self.assertAlmostEqual(
            snap.q_net_w,
            snap.q_solar_w
            + snap.q_earth_ir_w
            + snap.q_albedo_w
            + snap.q_internal_w
            - snap.q_radiated_w,
            places=12,
        )

    def test_csv_matches_heat_flow_internal_power(self) -> None:
        request = _base_3u_request(orbit_count=1, time_step_s=30.0)
        study = run_single_mode(request)
        curve = study.primary
        schedule = power_schedule_from_request(curve.request)
        csv_text = temperature_history_csv((curve,))
        lines = csv_text.strip().splitlines()[1:]
        # Spot-check first and mid samples against heat_flow_at_index.
        for index in (0, len(curve.result.time_s) // 2):
            snap = heat_flow_at_index(
                curve.result,
                index,
                curve.thermal,
                curve.orbit,
                curve.request.include_earth_infrared,
                curve.request.include_albedo,
                curve.earth_infrared,
                curve.albedo,
                thermal_model=curve.request.thermal_model,
                geometry=geometry_from_request(curve.request),
                attitude_mode=curve.request.attitude_mode,
                power_schedule=schedule,
            )
            # Find CSV row with matching time.
            matched = None
            for line in lines:
                fields = line.split(",")
                if math.isclose(float(fields[1]), snap.time_s, abs_tol=1e-6):
                    matched = fields
                    break
            self.assertIsNotNone(matched)
            assert matched is not None
            self.assertAlmostEqual(float(matched[5]), snap.q_internal_w, places=5)


class Checkpoint6OrbitGeometry(unittest.TestCase):
    def test_independent_period_and_critical_beta(self) -> None:
        orbit = CircularOrbit(altitude_m=500_000.0, beta_rad=0.0).validated()
        self.assertAlmostEqual(
            orbital_period_s(orbit),
            _independent_period_s(500_000.0),
            places=9,
        )
        self.assertAlmostEqual(
            critical_beta_rad(orbit),
            _independent_critical_beta_rad(500_000.0),
            places=12,
        )
        self.assertAlmostEqual(
            math.degrees(critical_beta_rad(orbit)),
            68.00711843616867,
            places=8,
        )

    def test_beta_symmetry_and_high_beta_zero_eclipse(self) -> None:
        for beta_deg in (0.0, 60.0, -60.0, 90.0, -90.0):
            orbit = CircularOrbit(
                altitude_m=500_000.0,
                beta_rad=math.radians(beta_deg),
            ).validated()
            duration = analytical_eclipse_duration_s(orbit)
            if abs(beta_deg) >= math.degrees(_independent_critical_beta_rad(500_000.0)):
                self.assertEqual(duration, 0.0)
            if abs(beta_deg) == 60.0:
                twin = CircularOrbit(
                    altitude_m=500_000.0,
                    beta_rad=math.radians(-beta_deg),
                ).validated()
                self.assertAlmostEqual(
                    analytical_eclipse_duration_s(twin),
                    duration,
                    places=12,
                )

    def test_near_critical_beta_edge(self) -> None:
        beta_c = _independent_critical_beta_rad(500_000.0)
        below = CircularOrbit(altitude_m=500_000.0, beta_rad=beta_c - 1e-4).validated()
        above = CircularOrbit(altitude_m=500_000.0, beta_rad=beta_c + 1e-4).validated()
        self.assertGreater(analytical_eclipse_duration_s(below), 0.0)
        self.assertEqual(analytical_eclipse_duration_s(above), 0.0)

    def test_sun_direction_and_right_handed_attitudes(self) -> None:
        for beta in (0.0, math.radians(60.0), math.radians(-90.0)):
            sun = sun_direction(beta)
            self.assertAlmostEqual(math.sqrt(sum(v * v for v in sun)), 1.0, places=12)
            self.assertAlmostEqual(sun[0], math.cos(beta), places=12)
            self.assertAlmostEqual(sun[2], math.sin(beta), places=12)
        # Nadir-pointing triad at theta=0.
        body_x, body_y, body_z = body_axes_inertial(
            AttitudeMode.NADIR_POINTING,
            0.0,
            sun_direction(0.0),
        )
        self.assertAlmostEqual(
            body_x[0] * (body_y[1] * body_z[2] - body_y[2] * body_z[1])
            + body_x[1] * (body_y[2] * body_z[0] - body_y[0] * body_z[2])
            + body_x[2] * (body_y[0] * body_z[1] - body_y[1] * body_z[0]),
            1.0,
            places=12,
        )
        # Sun-pointing at beta=90° exercises singularity fallback path.
        sx, sy, sz = body_axes_inertial(
            AttitudeMode.SUN_POINTING,
            0.0,
            sun_direction(math.radians(90.0)),
        )
        for axis in (sx, sy, sz):
            self.assertAlmostEqual(math.sqrt(sum(v * v for v in axis)), 1.0, places=10)

    def test_face_areas_independent_of_helper_repeat(self) -> None:
        length, width, height = 0.1, 0.1, 0.3405
        # Independent formulas (not calling RectangularBusGeometry.face_area_m2).
        a_x = width * height
        a_y = length * height
        a_z = length * width
        total = 2.0 * (a_x + a_y + a_z)
        derived = derived_face_areas_m2(length, width, height)
        self.assertAlmostEqual(derived["+x"], a_x, places=15)
        self.assertAlmostEqual(derived["+y"], a_y, places=15)
        self.assertAlmostEqual(derived["+z"], a_z, places=15)
        self.assertAlmostEqual(total_exterior_area_m2(length, width, height), total, places=15)
        geom = RectangularBusGeometry(
            length_m=length, width_m=width, height_m=height
        ).validated()
        for name in FACE_NAMES:
            self.assertAlmostEqual(geom.face_area_m2(name), derived[name], places=15)

    def test_projected_area_bounds(self) -> None:
        geom = RectangularBusGeometry(
            length_m=0.1, width_m=0.1, height_m=0.3405
        ).validated()
        area = projected_solar_area_m2(
            geom,
            body_x=(1.0, 0.0, 0.0),
            body_y=(0.0, 1.0, 0.0),
            body_z=(0.0, 0.0, 1.0),
            sun_direction_inertial=(1.0, 0.0, 0.0),
        )
        self.assertAlmostEqual(area, 0.1 * 0.3405, places=12)
        self.assertLessEqual(area, geom.total_exterior_area_m2() / 2.0 + 1e-12)


class Checkpoint6Convergence(unittest.TestCase):
    def test_timestep_convergence_nominal_3u(self) -> None:
        finals = {}
        for dt in (10.0, 5.0, 2.0, 1.0):
            result = run_gui_simulation(
                _base_3u_request(orbit_count=2, time_step_s=dt)
            )
            finals[dt] = temperature_metrics_c(result)["final_c"]
        # Eclipse-boundary sampling makes convergence non-monotonic in dt, but
        # all practical steps stay close to the 1 s reference for this case.
        reference = finals[1.0]
        for dt, value in finals.items():
            self.assertLess(abs(value - reference), 0.05, msg=f"dt={dt}")

    def test_eclipse_boundary_sampling_sensitivity(self) -> None:
        # Eclipse edges are sampled, not event-split: coarse vs fine can differ.
        coarse = run_gui_simulation(_base_3u_request(orbit_count=1, time_step_s=30.0))
        fine = run_gui_simulation(_base_3u_request(orbit_count=1, time_step_s=1.0))
        delta = abs(
            temperature_metrics_c(coarse)["final_c"]
            - temperature_metrics_c(fine)["final_c"]
        )
        # Documented class of limitation: differences remain modest for this case.
        self.assertLess(delta, 0.5)


class Checkpoint6LegacyBaselines(unittest.TestCase):
    def test_v1_environment_cases(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
