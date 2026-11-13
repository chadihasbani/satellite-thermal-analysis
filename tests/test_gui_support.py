"""Tests for GUI input assembly and solver wiring."""

from __future__ import annotations

import unittest

from satellite_thermal.gui_support import (
    GuiRunRequest,
    build_model_inputs,
    default_gui_request,
    request_fingerprint,
    run_gui_simulation,
    temperature_metrics_c,
    validate_gui_request,
)
from satellite_thermal.orbital_simulation import simulate_orbital_eclipse
from satellite_thermal.parameters import Phase1Parameters


class GuiSupportTests(unittest.TestCase):
    def test_defaults_match_phase3b_baseline_thermal_values(self) -> None:
        request = default_gui_request()
        thermal, orbit, earth_ir, albedo = build_model_inputs(request)
        self.assertEqual(thermal.mass_kg, 5.0)
        self.assertEqual(thermal.absorptivity, 0.60)
        self.assertEqual(thermal.emissivity, 0.80)
        self.assertEqual(thermal.internal_heat_w, 5.0)
        self.assertEqual(orbit.altitude_m, 500_000.0)
        self.assertEqual(earth_ir.infrared_absorptivity, thermal.emissivity)
        self.assertEqual(albedo.earth_bond_albedo, 0.30)
        self.assertTrue(request.include_earth_infrared)
        self.assertTrue(request.include_albedo)

    def test_kirchhoff_pairs_emissivity_to_infrared_absorptivity(self) -> None:
        request = default_gui_request()
        request = GuiRunRequest(**{**request.__dict__, "emissivity": 0.55})
        _, _, earth_ir, _ = build_model_inputs(request)
        self.assertEqual(earth_ir.infrared_absorptivity, 0.55)

    def test_gui_run_matches_direct_solver_call(self) -> None:
        request = default_gui_request()
        request = GuiRunRequest(
            **{
                **request.__dict__,
                "orbit_count": 1,
                "time_step_s": 30.0,
            }
        )
        from_gui = run_gui_simulation(request)
        thermal, orbit, earth_ir, albedo = build_model_inputs(request)
        direct = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=30.0,
            parameters=thermal,
            orbit=orbit,
            include_earth_infrared=True,
            earth_infrared=earth_ir,
            include_albedo=True,
            albedo=albedo,
        )
        self.assertEqual(from_gui.temperature_k, direct.temperature_k)
        metrics = temperature_metrics_c(from_gui)
        self.assertAlmostEqual(metrics["initial_c"], 20.0, places=8)

    def test_rejects_non_positive_orbit_count(self) -> None:
        request = GuiRunRequest(**{**default_gui_request().__dict__, "orbit_count": 0})
        with self.assertRaises(ValueError):
            run_gui_simulation(request)

    def test_rejects_temperature_at_or_below_absolute_zero(self) -> None:
        request = GuiRunRequest(
            **{**default_gui_request().__dict__, "initial_temperature_c": -273.15}
        )
        with self.assertRaises(ValueError):
            validate_gui_request(request)

    def test_rejects_negative_internal_heat(self) -> None:
        request = GuiRunRequest(
            **{**default_gui_request().__dict__, "internal_heat_w": -1.0}
        )
        with self.assertRaises(ValueError):
            validate_gui_request(request)

    def test_rejects_excessive_sample_count(self) -> None:
        request = GuiRunRequest(
            **{
                **default_gui_request().__dict__,
                "orbit_count": 20,
                "time_step_s": 0.1,
            }
        )
        with self.assertRaises(ValueError):
            validate_gui_request(request)

    def test_fingerprint_changes_when_mass_changes(self) -> None:
        base = default_gui_request()
        modified = GuiRunRequest(**{**base.__dict__, "mass_kg": 8.0})
        self.assertNotEqual(
            request_fingerprint("single", base),
            request_fingerprint("single", modified),
        )

    def test_phase1_defaults_unchanged(self) -> None:
        settings = Phase1Parameters()
        self.assertEqual(settings.projected_area_m2, 0.01)
        self.assertEqual(settings.radiating_area_m2, 0.06)


if __name__ == "__main__":
    unittest.main()
