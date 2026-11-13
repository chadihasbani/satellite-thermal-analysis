"""Phase 3B orbital time-step convergence checks."""

from __future__ import annotations

import unittest

from satellite_thermal.phase3b_convergence import run_phase3b_timestep_convergence


class Phase3bConvergenceTests(unittest.TestCase):
    def test_finer_steps_stay_close_on_final_temperature(self) -> None:
        # Use a short study in unit tests for runtime; full 5-orbit table is
        # available from verify_phase3b_convergence.py.
        rows = run_phase3b_timestep_convergence(
            orbit_count=1,
            time_steps_s=(10.0, 5.0, 1.0),
            reference_step_s=1.0,
        )
        by_step = {row.time_step_s: row for row in rows}
        self.assertEqual(by_step[1.0].delta_final_k, 0.0)
        self.assertLess(abs(by_step[5.0].delta_final_k), 0.05)
        self.assertLess(abs(by_step[10.0].delta_final_k), 0.2)
        self.assertGreater(
            abs(by_step[10.0].delta_final_k),
            abs(by_step[5.0].delta_final_k),
        )


if __name__ == "__main__":
    unittest.main()
