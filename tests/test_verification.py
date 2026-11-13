"""Checks for analytical equilibrium, zero net heat, and time-step convergence."""

from __future__ import annotations

import math
import unittest

from satellite_thermal.equilibrium import (
    analytical_equilibrium_temperature,
    equilibrium_temperature_k,
    net_heat_w,
)
from satellite_thermal.heat_transfer import temperature_derivative
from satellite_thermal.parameters import STEFAN_BOLTZMANN, Phase1Parameters
from satellite_thermal.units import kelvin_to_celsius
from satellite_thermal.verification import (
    CONVERGENCE_DURATION_S,
    approach_equilibrium,
    time_step_convergence,
)


# Written from the defining expression, not copied from the function output.
# Q_solar = 0.60 * 0.01 * 1361 = 8.166 W
# Q_solar + Q_internal = 13.166 W
# denominator = 0.80 * 5.670374419e-8 * 0.06
INDEPENDENT_HEAT_INPUT_W = 0.60 * 0.01 * 1361.0 + 5.0
INDEPENDENT_DENOMINATOR = 0.80 * STEFAN_BOLTZMANN * 0.06
INDEPENDENT_EQUILIBRIUM_K = (INDEPENDENT_HEAT_INPUT_W / INDEPENDENT_DENOMINATOR) ** 0.25


class AnalyticalEquilibriumTests(unittest.TestCase):
    def test_default_parameters_are_unchanged(self) -> None:
        settings = Phase1Parameters()
        self.assertEqual(settings.mass_kg, 5.0)
        self.assertEqual(settings.specific_heat_j_per_kg_k, 900.0)
        self.assertEqual(settings.initial_temperature_k, 293.15)
        self.assertEqual(settings.solar_flux_w_per_m2, 1361.0)
        self.assertEqual(settings.absorptivity, 0.60)
        self.assertEqual(settings.emissivity, 0.80)
        self.assertEqual(settings.projected_area_m2, 0.01)
        self.assertEqual(settings.radiating_area_m2, 0.06)
        self.assertEqual(settings.internal_heat_w, 5.0)
        self.assertEqual(settings.stefan_boltzmann_w_per_m2_k4, STEFAN_BOLTZMANN)

    def test_equilibrium_matches_the_independent_fourth_root(self) -> None:
        from_components = equilibrium_temperature_k(
            solar_heat_w=0.60 * 0.01 * 1361.0,
            internal_heat_w=5.0,
            emissivity=0.80,
            radiating_area_m2=0.06,
            stefan_boltzmann_w_per_m2_k4=STEFAN_BOLTZMANN,
        )
        from_parameters = analytical_equilibrium_temperature(Phase1Parameters())
        self.assertTrue(
            math.isclose(from_components, INDEPENDENT_EQUILIBRIUM_K, rel_tol=0.0, abs_tol=1e-12)
        )
        self.assertTrue(
            math.isclose(from_parameters, INDEPENDENT_EQUILIBRIUM_K, rel_tol=0.0, abs_tol=1e-12)
        )
        self.assertTrue(math.isclose(from_parameters, 263.72, rel_tol=0.0, abs_tol=5e-3))
        self.assertTrue(
            math.isclose(kelvin_to_celsius(from_parameters), -9.43, rel_tol=0.0, abs_tol=5e-3)
        )


class ZeroNetHeatTests(unittest.TestCase):
    def test_emission_balances_heat_input_at_equilibrium(self) -> None:
        settings = Phase1Parameters()
        equilibrium_k = INDEPENDENT_EQUILIBRIUM_K
        residual_w = net_heat_w(equilibrium_k, settings)
        self.assertTrue(math.isclose(residual_w, 0.0, rel_tol=0.0, abs_tol=1e-9))

    def test_temperature_derivative_is_zero_at_equilibrium(self) -> None:
        settings = Phase1Parameters()
        rate_k_per_s = temperature_derivative(
            temperature_k=INDEPENDENT_EQUILIBRIUM_K,
            mass_kg=settings.mass_kg,
            specific_heat_j_per_kg_k=settings.specific_heat_j_per_kg_k,
            absorptivity=settings.absorptivity,
            projected_area_m2=settings.projected_area_m2,
            solar_flux_w_per_m2=settings.solar_flux_w_per_m2,
            internal_heat_w=settings.internal_heat_w,
            emissivity=settings.emissivity,
            radiating_area_m2=settings.radiating_area_m2,
            stefan_boltzmann_w_per_m2_k4=settings.stefan_boltzmann_w_per_m2_k4,
        )
        self.assertTrue(math.isclose(rate_k_per_s, 0.0, rel_tol=0.0, abs_tol=1e-12))


class NumericalConvergenceTests(unittest.TestCase):
    def test_long_run_finishes_near_the_analytical_equilibrium(self) -> None:
        approach = approach_equilibrium(Phase1Parameters())
        self.assertGreater(approach.duration_s, 10.0 * approach.time_constant_s)
        self.assertLess(abs(approach.difference_k), 1e-3)
        self.assertLess(approach.final_temperature_k, 293.15)

    def test_finer_steps_move_closer_to_the_tenth_second_result(self) -> None:
        results = time_step_convergence(
            duration_s=CONVERGENCE_DURATION_S,
            parameters=Phase1Parameters(),
        )
        by_step = {item.time_step_s: item for item in results}
        self.assertEqual(tuple(by_step), (10.0, 1.0, 0.5, 0.1))
        self.assertEqual(by_step[0.1].difference_from_reference_k, 0.0)
        self.assertGreater(
            abs(by_step[10.0].difference_from_reference_k),
            abs(by_step[1.0].difference_from_reference_k),
        )
        self.assertGreater(
            abs(by_step[1.0].difference_from_reference_k),
            abs(by_step[0.5].difference_from_reference_k),
        )
        # The 90-minute window is a fraction of the radiative time constant,
        # so a 1 s step already agrees with 0.1 s well inside 0.01 K.
        self.assertLess(abs(by_step[1.0].difference_from_reference_k), 1e-2)
        self.assertLess(abs(by_step[0.5].difference_from_reference_k), 1e-2)
        for item in results:
            self.assertGreater(item.final_temperature_k, INDEPENDENT_EQUILIBRIUM_K)
            self.assertLess(item.final_temperature_k, 293.15)


if __name__ == "__main__":
    unittest.main()
