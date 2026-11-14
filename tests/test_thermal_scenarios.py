"""Tests for Checkpoint 4 thermal screening scenarios."""

from __future__ import annotations

import math
import unittest

from satellite_thermal.gui_support import (
    GuiRunRequest,
    all_curves,
    apply_thermal_scenario,
    default_gui_request,
    run_baseline_comparison_mode,
    run_environment_comparison_mode,
    run_gui_simulation,
    run_scenario_comparison_mode,
    run_single_mode,
    scenario_comparison_summary_rows,
    temperature_history_csv,
    temperature_metrics_c,
)
from satellite_thermal.heat_flows import heat_flow_at_index
from satellite_thermal.orbit import CircularOrbit, analytical_eclipse_duration_s, critical_beta_rad
from satellite_thermal.thermal_scenarios import (
    NASA_PP_ALBEDO_COLD,
    NASA_PP_ALBEDO_HOT,
    NASA_PP_SOLAR_SUMMER_W_PER_M2,
    NASA_PP_SOLAR_WINTER_W_PER_M2,
    REPO_NOMINAL_ALBEDO,
    REPO_NOMINAL_OLR_W_PER_M2,
    REPO_NOMINAL_SOLAR_W_PER_M2,
    SCENARIO_CASE_COLD,
    SCENARIO_CASE_HOT,
    SCENARIO_CASE_NOMINAL,
    ThermalScenarioId,
    build_scenario_definition,
    earth_olr_energy_balance_w_per_m2,
    hot_case_beta_deg,
    mismatched_preset_field_names,
    parse_thermal_scenario_id,
    preset_controls_locked,
    scenario_controlled_field_names,
    scenario_overlay_fields,
    sync_session_values_from_scenario,
)


class ScenarioDefinitionTests(unittest.TestCase):
    def test_preset_environmental_values(self) -> None:
        nominal = build_scenario_definition(ThermalScenarioId.NOMINAL, 500.0)
        hot = build_scenario_definition(ThermalScenarioId.HOT, 500.0)
        cold = build_scenario_definition(ThermalScenarioId.COLD, 500.0)

        self.assertEqual(nominal.solar_flux_w_per_m2, REPO_NOMINAL_SOLAR_W_PER_M2)
        self.assertEqual(nominal.earth_bond_albedo, REPO_NOMINAL_ALBEDO)
        self.assertEqual(nominal.earth_olr_w_per_m2, REPO_NOMINAL_OLR_W_PER_M2)
        self.assertEqual(nominal.beta_deg, 0.0)
        self.assertEqual(nominal.internal_heat_w, 5.0)

        self.assertEqual(hot.solar_flux_w_per_m2, NASA_PP_SOLAR_WINTER_W_PER_M2)
        self.assertEqual(hot.earth_bond_albedo, NASA_PP_ALBEDO_HOT)
        self.assertAlmostEqual(
            hot.earth_olr_w_per_m2,
            earth_olr_energy_balance_w_per_m2(
                NASA_PP_SOLAR_WINTER_W_PER_M2, NASA_PP_ALBEDO_HOT
            ),
            places=12,
        )
        self.assertEqual(hot.internal_heat_w, 15.0)
        self.assertGreater(hot.beta_deg, math.degrees(critical_beta_rad(CircularOrbit())))

        self.assertEqual(cold.solar_flux_w_per_m2, NASA_PP_SOLAR_SUMMER_W_PER_M2)
        self.assertEqual(cold.earth_bond_albedo, NASA_PP_ALBEDO_COLD)
        self.assertAlmostEqual(
            cold.earth_olr_w_per_m2,
            earth_olr_energy_balance_w_per_m2(
                NASA_PP_SOLAR_SUMMER_W_PER_M2, NASA_PP_ALBEDO_COLD
            ),
            places=12,
        )
        self.assertEqual(cold.beta_deg, 0.0)
        self.assertEqual(cold.internal_heat_w, 1.0)
        # Energy-balance cold OLR exceeds hot OLR.
        self.assertGreater(cold.earth_olr_w_per_m2, hot.earth_olr_w_per_m2)

    def test_hot_beta_tracks_altitude_critical_value(self) -> None:
        beta_500 = hot_case_beta_deg(500.0)
        beta_800 = hot_case_beta_deg(800.0)
        c500 = math.degrees(critical_beta_rad(CircularOrbit(altitude_m=500_000.0)))
        c800 = math.degrees(critical_beta_rad(CircularOrbit(altitude_m=800_000.0)))
        self.assertGreater(beta_500, c500)
        self.assertGreater(beta_800, c800)
        self.assertLess(beta_800, beta_500)

    def test_custom_has_no_definition_table(self) -> None:
        with self.assertRaises(ValueError):
            build_scenario_definition(ThermalScenarioId.CUSTOM)


class ScenarioApplicationTests(unittest.TestCase):
    def test_apply_preserves_geometry_and_coatings(self) -> None:
        base = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "mass_kg": 7.5,
                "absorptivity": 0.42,
                "emissivity": 0.77,
                "projected_area_m2": 0.02,
                "body_length_m": 0.2,
                "thermal_model": "enhanced",
                "attitude_mode": "nadir_pointing",
                "altitude_km": 600.0,
            }
        )
        hot = apply_thermal_scenario(base, ThermalScenarioId.HOT)
        for field in (
            "mass_kg",
            "absorptivity",
            "emissivity",
            "projected_area_m2",
            "body_length_m",
            "thermal_model",
            "attitude_mode",
            "altitude_km",
            "orbit_count",
            "time_step_s",
        ):
            self.assertEqual(getattr(hot, field), getattr(base, field), field)
        self.assertEqual(hot.solar_flux_w_per_m2, NASA_PP_SOLAR_WINTER_W_PER_M2)
        self.assertEqual(hot.power_schedule_kind, "constant")
        self.assertNotEqual(hot.beta_deg, base.beta_deg)

    def test_custom_is_identity(self) -> None:
        base = default_gui_request()
        self.assertEqual(apply_thermal_scenario(base, "custom"), base)

    def test_controlled_field_names_are_explicit(self) -> None:
        names = scenario_controlled_field_names()
        self.assertIn("solar_flux_w_per_m2", names)
        self.assertIn("beta_deg", names)
        self.assertIn("internal_heat_w", names)
        self.assertNotIn("mass_kg", names)
        self.assertNotIn("absorptivity", names)


class ScenarioPhysicsTests(unittest.TestCase):
    def test_hot_case_has_no_analytical_eclipse(self) -> None:
        hot = apply_thermal_scenario(default_gui_request(), ThermalScenarioId.HOT)
        orbit = CircularOrbit(
            altitude_m=hot.altitude_km * 1000.0,
            beta_rad=math.radians(hot.beta_deg),
        ).validated()
        self.assertEqual(analytical_eclipse_duration_s(orbit), 0.0)
        result = run_gui_simulation(hot)
        self.assertFalse(any(result.in_eclipse))

    def test_cold_and_nominal_retain_eclipse_at_beta_zero(self) -> None:
        for scenario in (ThermalScenarioId.COLD, ThermalScenarioId.NOMINAL):
            req = apply_thermal_scenario(default_gui_request(), scenario)
            self.assertEqual(req.beta_deg, 0.0)
            result = run_gui_simulation(
                GuiRunRequest(**{**req.__dict__, "orbit_count": 1, "time_step_s": 30.0})
            )
            self.assertTrue(any(result.in_eclipse))

    def test_scenario_ordering_of_final_temperatures(self) -> None:
        base = GuiRunRequest(
            **{**default_gui_request().__dict__, "orbit_count": 5, "time_step_s": 5.0}
        )
        metrics = {}
        for scenario in (
            ThermalScenarioId.COLD,
            ThermalScenarioId.NOMINAL,
            ThermalScenarioId.HOT,
        ):
            result = run_gui_simulation(apply_thermal_scenario(base, scenario))
            metrics[scenario] = temperature_metrics_c(result)
        self.assertLess(metrics[ThermalScenarioId.COLD]["final_c"], metrics[ThermalScenarioId.NOMINAL]["final_c"])
        self.assertLess(metrics[ThermalScenarioId.NOMINAL]["final_c"], metrics[ThermalScenarioId.HOT]["final_c"])
        self.assertLess(metrics[ThermalScenarioId.COLD]["minimum_c"], metrics[ThermalScenarioId.HOT]["minimum_c"])

    def test_energy_balance_and_heat_flow_consistency(self) -> None:
        req = apply_thermal_scenario(
            GuiRunRequest(**{**default_gui_request().__dict__, "orbit_count": 1, "time_step_s": 20.0}),
            ThermalScenarioId.HOT,
        )
        named = run_single_mode(req).primary
        snap = heat_flow_at_index(
            named.result,
            0,
            named.thermal,
            named.orbit,
            named.request.include_earth_infrared,
            named.request.include_albedo,
            named.earth_infrared,
            named.albedo,
            power_schedule=None,
        )
        self.assertAlmostEqual(
            snap.q_net_w,
            snap.q_solar_w
            + snap.q_earth_ir_w
            + snap.q_albedo_w
            + snap.q_internal_w
            - snap.q_radiated_w,
            places=12,
        )
        self.assertAlmostEqual(snap.q_internal_w, 15.0, places=12)


class ScenarioGuiModeTests(unittest.TestCase):
    def test_scenario_compare_mode_reproducible(self) -> None:
        request = GuiRunRequest(
            **{**default_gui_request().__dict__, "orbit_count": 2, "time_step_s": 10.0}
        )
        first = run_scenario_comparison_mode(request)
        second = run_scenario_comparison_mode(request)
        curves_a = all_curves(first)
        curves_b = all_curves(second)
        self.assertEqual([c.name for c in curves_a], list(
            (SCENARIO_CASE_COLD, SCENARIO_CASE_NOMINAL, SCENARIO_CASE_HOT)
        ))
        for left, right in zip(curves_a, curves_b):
            self.assertEqual(left.result.temperature_k, right.result.temperature_k)
        rows = scenario_comparison_summary_rows(curves_a)
        self.assertEqual(len(rows), 3)

    def test_all_gui_modes_accept_hot_overlay(self) -> None:
        request = apply_thermal_scenario(
            GuiRunRequest(**{**default_gui_request().__dict__, "orbit_count": 1, "time_step_s": 30.0}),
            ThermalScenarioId.HOT,
        )
        single = run_single_mode(request)
        baseline = run_baseline_comparison_mode(request)
        environment = run_environment_comparison_mode(request)
        self.assertEqual(single.primary.request.solar_flux_w_per_m2, NASA_PP_SOLAR_WINTER_W_PER_M2)
        self.assertEqual(baseline.primary.request.beta_deg, request.beta_deg)
        # Reference stays on defaults; Modified carries the hot overlay.
        self.assertEqual(baseline.companions[0].request.solar_flux_w_per_m2, REPO_NOMINAL_SOLAR_W_PER_M2)
        self.assertEqual(environment.primary.request.solar_flux_w_per_m2, NASA_PP_SOLAR_WINTER_W_PER_M2)

    def test_csv_export_includes_all_scenario_curves(self) -> None:
        request = GuiRunRequest(
            **{**default_gui_request().__dict__, "orbit_count": 1, "time_step_s": 60.0}
        )
        csv_text = temperature_history_csv(all_curves(run_scenario_comparison_mode(request)))
        self.assertIn(SCENARIO_CASE_COLD, csv_text)
        self.assertIn(SCENARIO_CASE_NOMINAL, csv_text)
        self.assertIn(SCENARIO_CASE_HOT, csv_text)
        self.assertIn("q_internal_w", csv_text)

    def test_legacy_baselines_preserved_under_nominal(self) -> None:
        request = apply_thermal_scenario(
            GuiRunRequest(
                **{
                    **default_gui_request().__dict__,
                    "orbit_count": 5,
                    "time_step_s": 1.0,
                    "thermal_model": "legacy",
                }
            ),
            ThermalScenarioId.NOMINAL,
        )
        finals = [
            temperature_metrics_c(curve.result)["final_c"]
            for curve in all_curves(run_environment_comparison_mode(request))
        ]
        self.assertAlmostEqual(finals[0], -12.5661, places=3)
        self.assertAlmostEqual(finals[1], -6.8313, places=3)
        self.assertAlmostEqual(finals[2], -4.5386, places=3)

    def test_parse_rejects_unknown_scenario(self) -> None:
        with self.assertRaises(ValueError):
            parse_thermal_scenario_id("scorching")


class ScenarioEventAwareStillWorksTests(unittest.TestCase):
    def test_custom_scenario_keeps_event_aware_power(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "orbit_count": 1,
                "time_step_s": 5.0,
                "power_schedule_kind": "custom_intervals",
                "custom_intervals_text": "1,2,100",
                "internal_heat_w": 5.0,
            }
        )
        custom = apply_thermal_scenario(request, ThermalScenarioId.CUSTOM)
        result = run_gui_simulation(custom)
        self.assertTrue(any(math.isclose(t, 1.0, abs_tol=1e-12) for t in result.time_s))
        self.assertTrue(any(math.isclose(t, 2.0, abs_tol=1e-12) for t in result.time_s))


class ScenarioGuiConsistencyTests(unittest.TestCase):
    def test_preset_controls_lock_rules(self) -> None:
        self.assertTrue(preset_controls_locked(ThermalScenarioId.HOT))
        self.assertTrue(preset_controls_locked(ThermalScenarioId.COLD))
        self.assertTrue(preset_controls_locked(ThermalScenarioId.NOMINAL))
        self.assertFalse(preset_controls_locked(ThermalScenarioId.CUSTOM))
        self.assertTrue(
            preset_controls_locked(ThermalScenarioId.CUSTOM, mode="scenario_compare")
        )

    def test_synced_session_matches_solver_overlay(self) -> None:
        for scenario in (
            ThermalScenarioId.NOMINAL,
            ThermalScenarioId.HOT,
            ThermalScenarioId.COLD,
        ):
            for altitude_km in (500.0, 800.0):
                session = sync_session_values_from_scenario(scenario, altitude_km)
                field_values = {
                    name.removeprefix("gui_"): value for name, value in session.items()
                }
                self.assertEqual(
                    mismatched_preset_field_names(field_values, scenario, altitude_km),
                    (),
                )
                base = GuiRunRequest(
                    **{**default_gui_request().__dict__, "altitude_km": altitude_km}
                )
                # Simulate a stale / contradictory sidebar edit.
                tampered = GuiRunRequest(
                    **{
                        **base.__dict__,
                        "internal_heat_w": 8.0,
                        "solar_flux_w_per_m2": 1000.0,
                        "beta_deg": 12.0,
                    }
                )
                applied = apply_thermal_scenario(tampered, scenario)
                expected = scenario_overlay_fields(
                    build_scenario_definition(scenario, altitude_km)
                )
                for name, value in expected.items():
                    self.assertEqual(getattr(applied, name), value, name)
                tampered_fields = {**tampered.__dict__}
                self.assertIn(
                    "internal_heat_w",
                    mismatched_preset_field_names(
                        tampered_fields, scenario, altitude_km
                    ),
                )

    def test_custom_allows_user_values_without_mismatch(self) -> None:
        fields = {
            **default_gui_request().__dict__,
            "internal_heat_w": 8.0,
            "solar_flux_w_per_m2": 1400.0,
            "beta_deg": 15.0,
        }
        self.assertEqual(
            mismatched_preset_field_names(fields, ThermalScenarioId.CUSTOM, 500.0),
            (),
        )
        applied = apply_thermal_scenario(
            GuiRunRequest(**fields), ThermalScenarioId.CUSTOM
        )
        self.assertEqual(applied.internal_heat_w, 8.0)
        self.assertEqual(applied.solar_flux_w_per_m2, 1400.0)
        self.assertEqual(applied.beta_deg, 15.0)

    def test_hot_beta_session_updates_with_altitude(self) -> None:
        low = sync_session_values_from_scenario(ThermalScenarioId.HOT, 500.0)
        high = sync_session_values_from_scenario(ThermalScenarioId.HOT, 800.0)
        self.assertEqual(low["gui_beta_deg"], hot_case_beta_deg(500.0))
        self.assertEqual(high["gui_beta_deg"], hot_case_beta_deg(800.0))
        self.assertNotEqual(low["gui_beta_deg"], high["gui_beta_deg"])

    def test_scenario_switching_hot_cold_custom_session_values(self) -> None:
        hot = sync_session_values_from_scenario(ThermalScenarioId.HOT, 500.0)
        cold = sync_session_values_from_scenario(ThermalScenarioId.COLD, 500.0)
        self.assertEqual(hot["gui_internal_heat_w"], 15.0)
        self.assertEqual(cold["gui_internal_heat_w"], 1.0)
        self.assertEqual(hot["gui_solar_flux_w_per_m2"], NASA_PP_SOLAR_WINTER_W_PER_M2)
        self.assertEqual(cold["gui_solar_flux_w_per_m2"], NASA_PP_SOLAR_SUMMER_W_PER_M2)
        self.assertEqual(sync_session_values_from_scenario(ThermalScenarioId.CUSTOM, 500.0), {})

    def test_scenario_compare_shares_spacecraft_properties(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "mass_kg": 7.25,
                "absorptivity": 0.55,
                "emissivity": 0.72,
                "body_length_m": 0.15,
                "projected_area_m2": 0.015,
                "thermal_model": "enhanced",
                "attitude_mode": "sun_pointing",
                "orbit_count": 1,
                "time_step_s": 30.0,
                "altitude_km": 550.0,
            }
        )
        curves = all_curves(run_scenario_comparison_mode(request))
        self.assertEqual(len(curves), 3)
        for curve in curves:
            self.assertEqual(curve.request.mass_kg, 7.25)
            self.assertEqual(curve.request.absorptivity, 0.55)
            self.assertEqual(curve.request.emissivity, 0.72)
            self.assertEqual(curve.request.body_length_m, 0.15)
            self.assertEqual(curve.request.projected_area_m2, 0.015)
            self.assertEqual(curve.request.thermal_model, "enhanced")
            self.assertEqual(curve.request.attitude_mode, "sun_pointing")
            self.assertEqual(curve.request.altitude_km, 550.0)
        # Environmental / power overlays still differ by scenario.
        by_name = {curve.name: curve for curve in curves}
        self.assertEqual(by_name[SCENARIO_CASE_HOT].request.internal_heat_w, 15.0)
        self.assertEqual(by_name[SCENARIO_CASE_COLD].request.internal_heat_w, 1.0)
        self.assertEqual(by_name[SCENARIO_CASE_NOMINAL].request.internal_heat_w, 5.0)


if __name__ == "__main__":
    unittest.main()
