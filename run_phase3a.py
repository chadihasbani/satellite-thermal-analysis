"""Compare Phase 2 (no Earth IR) with Phase 3A (Earth IR on).

Phase 1 remains `python main.py`. Phase 2 alone remains `python run_phase2.py`.
This script keeps the same orbit, eclipse geometry, and thermal parameters.
Only the optional Earth-infrared term changes between the two histories.
Albedo is not included.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from satellite_thermal.comparison_plot import plot_phase2_phase3a_comparison
from satellite_thermal.earth_infrared import (
    EarthInfraredParameters,
    earth_infrared_heat_w,
    earth_view_factor,
)
from satellite_thermal.orbit import CircularOrbit
from satellite_thermal.orbital_simulation import simulate_orbital_eclipse
from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.units import kelvin_to_celsius

DEFAULT_PLOT = Path("outputs") / "phase3a_earth_ir_comparison.png"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 3A: compare five orbits without and with simplified "
            "Earth infrared heating."
        )
    )
    parser.add_argument(
        "--time-step",
        type=float,
        default=1.0,
        help="Explicit Euler time step in seconds (default: 1).",
    )
    parser.add_argument(
        "--orbits",
        type=int,
        default=5,
        help="Number of complete orbits (default: 5).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_PLOT,
        help="Where to save the comparison plot.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Open an interactive Matplotlib window after saving.",
    )
    return parser


def _stats(temperatures_k: tuple[float, ...]) -> tuple[float, float, float, float]:
    return (
        temperatures_k[0],
        min(temperatures_k),
        max(temperatures_k),
        temperatures_k[-1],
    )


def _print_case(label: str, temperatures_k: tuple[float, ...]) -> None:
    initial_k, minimum_k, maximum_k, final_k = _stats(temperatures_k)
    print(label)
    print(
        f"  Initial: {initial_k:.4f} K ({kelvin_to_celsius(initial_k):.4f} °C)"
    )
    print(
        f"  Minimum: {minimum_k:.4f} K ({kelvin_to_celsius(minimum_k):.4f} °C)"
    )
    print(
        f"  Maximum: {maximum_k:.4f} K ({kelvin_to_celsius(maximum_k):.4f} °C)"
    )
    print(
        f"  Final:   {final_k:.4f} K ({kelvin_to_celsius(final_k):.4f} °C)"
    )


def run(
    time_step_s: float = 1.0,
    orbit_count: int = 5,
    output_path: Path = DEFAULT_PLOT,
    show: bool = False,
) -> None:
    """Run Phase 2 and Phase 3A side by side and write the comparison plot."""
    thermal = Phase1Parameters().validated()
    orbit = CircularOrbit().validated()
    earth_ir = EarthInfraredParameters().validated()
    view_factor = earth_view_factor(orbit)
    q_earth_ir = earth_infrared_heat_w(orbit, earth_ir)

    phase2 = simulate_orbital_eclipse(
        orbit_count=orbit_count,
        time_step_s=time_step_s,
        parameters=thermal,
        orbit=orbit,
        include_earth_infrared=False,
    )
    phase3a = simulate_orbital_eclipse(
        orbit_count=orbit_count,
        time_step_s=time_step_s,
        parameters=thermal,
        orbit=orbit,
        include_earth_infrared=True,
        earth_infrared=earth_ir,
    )

    print("Phase 3A comparison: Earth infrared heating")
    print("Teaching result. Albedo is not included.")
    print(
        f"E_olr (illustrative TOA): {earth_ir.earth_olr_w_per_m2:.1f} W/m^2"
    )
    print(f"Earth view factor F_earth: {view_factor:.6f}")
    print(f"Earth-facing area A_earth: {earth_ir.earth_facing_area_m2:.4f} m^2")
    print(f"IR absorptivity alpha_ir: {earth_ir.infrared_absorptivity:.2f}")
    print(f"Q_earth_ir: {q_earth_ir:.6f} W")
    print(f"Orbits: {orbit_count}")
    print(f"Time step: {time_step_s:g} s")
    print()
    _print_case("Phase 2 (Earth IR off)", phase2.temperature_k)
    print()
    _print_case("Phase 3A (Earth IR on)", phase3a.temperature_k)
    print()

    p2_i, p2_min, p2_max, p2_f = _stats(phase2.temperature_k)
    p3_i, p3_min, p3_max, p3_f = _stats(phase3a.temperature_k)
    print("Differences (Phase 3A - Phase 2)")
    print(f"  Initial: {p3_i - p2_i:.6f} K")
    print(f"  Minimum: {p3_min - p2_min:.6f} K")
    print(f"  Maximum: {p3_max - p2_max:.6f} K")
    print(f"  Final:   {p3_f - p2_f:.6f} K")

    plot_phase2_phase3a_comparison(
        phase2, phase3a, output_path=output_path, show=show
    )
    print(f"Plot saved to: {output_path}")


def main() -> None:
    args = build_parser().parse_args()
    run(
        time_step_s=args.time_step,
        orbit_count=args.orbits,
        output_path=args.output,
        show=args.show,
    )


if __name__ == "__main__":
    main()
