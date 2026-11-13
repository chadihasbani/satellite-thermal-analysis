"""Phase 4 sensitivity study checks."""

from __future__ import annotations

import unittest

from satellite_thermal.orbital_simulation import simulate_orbital_eclipse
from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.sensitivity import (
    baseline_case,
    build_sensitivity_cases,
    run_sensitivity_case,
    run_sensitivity_study,
)


class SensitivityStudyTests(unittest.TestCase):
    def test_baseline_matches_phase3b_defaults(self) -> None:
        case = baseline_case()
        self.assertEqual(case.thermal.absorptivity, 0.60)
        self.assertEqual(case.thermal.emissivity, 0.80)
        self.assertEqual(case.thermal.internal_heat_w, 5.0)
        self.assertEqual(case.thermal.mass_kg, 5.0)
        self.assertEqual(case.thermal.radiating_area_m2, 0.06)
        self.assertEqual(case.orbit.altitude_m, 500_000.0)
        self.assertEqual(case.earth_infrared.infrared_absorptivity, 0.80)

        from_sensitivity = run_sensitivity_case(case, orbit_count=1, time_step_s=30.0)
        direct = simulate_orbital_eclipse(
            orbit_count=1,
            time_step_s=30.0,
            parameters=Phase1Parameters(),
            include_earth_infrared=True,
            include_albedo=True,
        )
        self.assertEqual(from_sensitivity.temperature_k, direct.temperature_k)
        self.assertTrue(from_sensitivity.include_albedo)
        self.assertGreater(from_sensitivity.earth_infrared_heat_w, 0.0)

    def test_higher_internal_power_raises_final_temperature(self) -> None:
        metrics = run_sensitivity_study(
            orbit_count=1,
            time_step_s=20.0,
            cases=tuple(
                case
                for case in build_sensitivity_cases()
                if case.case_id in {"baseline", "qint_0", "qint_10"}
            ),
        )
        by_id = {item.case_id: item for item in metrics}
        self.assertGreater(by_id["qint_10"].final_k, by_id["baseline"].final_k)
        self.assertLess(by_id["qint_0"].final_k, by_id["baseline"].final_k)

    def test_larger_radiating_area_lowers_final_temperature(self) -> None:
        metrics = run_sensitivity_study(
            orbit_count=1,
            time_step_s=20.0,
            cases=tuple(
                case
                for case in build_sensitivity_cases()
                if case.case_id in {"baseline", "arad_0.04", "arad_0.08"}
            ),
        )
        by_id = {item.case_id: item for item in metrics}
        self.assertGreater(by_id["arad_0.04"].final_k, by_id["baseline"].final_k)
        self.assertLess(by_id["arad_0.08"].final_k, by_id["baseline"].final_k)

    def test_emissivity_cases_keep_kirchhoff_pairing(self) -> None:
        cases = {
            case.case_id: case
            for case in build_sensitivity_cases()
            if case.group == "emissivity"
        }
        for case in cases.values():
            self.assertEqual(
                case.thermal.emissivity,
                case.earth_infrared.infrared_absorptivity,
            )

    def test_case_catalog_includes_expected_groups(self) -> None:
        cases = build_sensitivity_cases()
        groups = {case.group for case in cases}
        self.assertEqual(cases[0].case_id, "baseline")
        self.assertTrue(
            {
                "baseline",
                "absorptivity",
                "emissivity",
                "internal_power",
                "capacitance",
                "radiating_area",
                "altitude",
            }.issubset(groups)
        )


if __name__ == "__main__":
    unittest.main()
