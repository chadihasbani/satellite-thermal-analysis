"""Heat-flow snapshots and time-index helpers."""

from __future__ import annotations

import unittest

from satellite_thermal.gui_support import GuiRunRequest, default_gui_request, run_named_simulation
from satellite_thermal.heat_flows import heat_flow_at_index, nearest_sample_index
from satellite_thermal.orbit import orbital_period_s


class HeatFlowTests(unittest.TestCase):
    def test_eclipse_forces_solar_and_albedo_to_zero(self) -> None:
        named = run_named_simulation(
            "full",
            GuiRunRequest(
                **{
                    **default_gui_request().__dict__,
                    "orbit_count": 1,
                    "time_step_s": 20.0,
                    "include_earth_infrared": True,
                    "include_albedo": True,
                }
            ),
        )
        eclipse_index = next(
            index for index, flag in enumerate(named.result.in_eclipse) if flag
        )
        snap = heat_flow_at_index(
            named.result,
            eclipse_index,
            named.thermal,
            named.orbit,
            include_earth_infrared=True,
            include_albedo=True,
            earth_infrared=named.earth_infrared,
            albedo=named.albedo,
        )
        self.assertTrue(snap.in_eclipse)
        self.assertEqual(snap.q_solar_w, 0.0)
        self.assertEqual(snap.q_albedo_w, 0.0)
        self.assertGreater(snap.q_earth_ir_w, 0.0)
        self.assertEqual(snap.q_internal_w, named.thermal.internal_heat_w)
        self.assertAlmostEqual(
            snap.q_net_w,
            snap.q_solar_w
            + snap.q_earth_ir_w
            + snap.q_albedo_w
            + snap.q_internal_w
            - snap.q_radiated_w,
            places=12,
        )

    def test_sunlit_start_has_positive_solar(self) -> None:
        named = run_named_simulation(
            "full",
            GuiRunRequest(
                **{
                    **default_gui_request().__dict__,
                    "orbit_count": 1,
                    "time_step_s": 30.0,
                    "include_earth_infrared": True,
                    "include_albedo": True,
                }
            ),
        )
        snap = heat_flow_at_index(
            named.result,
            0,
            named.thermal,
            named.orbit,
            True,
            True,
            named.earth_infrared,
            named.albedo,
        )
        self.assertFalse(snap.in_eclipse)
        self.assertGreater(snap.q_solar_w, 0.0)
        self.assertGreater(snap.q_albedo_w, 0.0)

    def test_nearest_sample_index_round_trip(self) -> None:
        named = run_named_simulation(
            "full",
            GuiRunRequest(
                **{
                    **default_gui_request().__dict__,
                    "orbit_count": 1,
                    "time_step_s": 30.0,
                }
            ),
        )
        mid = len(named.result.time_s) // 2
        target = named.result.time_s[mid]
        self.assertEqual(nearest_sample_index(named.result, target), mid)
        period = orbital_period_s(named.orbit)
        self.assertGreater(period, 5000.0)


if __name__ == "__main__":
    unittest.main()
