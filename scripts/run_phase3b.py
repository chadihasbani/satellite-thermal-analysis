"""Compare Phase 3A (Earth IR) with Phase 3B (Earth IR + albedo)."""

from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap
from _bootstrap import ROOT

from satellite_thermal.albedo import (
    AlbedoParameters,
    albedo_geometry_factor,
    albedo_heating,
)
from satellite_thermal.comparison_plot import plot_phase3a_phase3b_comparison
from satellite_thermal.earth_infrared import earth_view_factor
from satellite_thermal.orbit import CircularOrbit
from satellite_thermal.orbital_simulation import simulate_orbital_eclipse
from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.units import kelvin_to_celsius

DEFAULT_PLOT = ROOT / "outputs" / "phase3b_albedo_comparison.png"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 3B: compare five orbits with Earth IR only versus "
            "Earth IR plus angle-dependent albedo."
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
    print(f"  Initial: {initial_k:.4f} K ({kelvin_to_celsius(initial_k):.4f} °C)")
    print(f"  Minimum: {minimum_k:.4f} K ({kelvin_to_celsius(minimum_k):.4f} °C)")
    print(f"  Maximum: {maximum_k:.4f} K ({kelvin_to_celsius(maximum_k):.4f} °C)")
    print(f"  Final:   {final_k:.4f} K ({kelvin_to_celsius(final_k):.4f} °C)")


def run(
    time_step_s: float = 1.0,
    orbit_count: int = 5,
    output_path: Path = DEFAULT_PLOT,
    show: bool = False,
) -> None:
    """Run Phase 3A and Phase 3B side by side and write the comparison plot."""
    thermal = Phase1Parameters().validated()
    orbit = CircularOrbit().validated()
    albedo = AlbedoParameters().validated()
    view = earth_view_factor(orbit)
    peak_factor = albedo_geometry_factor(0.0, view)
    peak_albedo_w = albedo_heating(
        solar_absorptivity=thermal.absorptivity,
        albedo_area_m2=albedo.albedo_area_m2,
        earth_bond_albedo=albedo.earth_bond_albedo,
        solar_flux_w_per_m2=thermal.solar_flux_w_per_m2,
        geometry_factor=peak_factor,
    )

    phase3a = simulate_orbital_eclipse(
        orbit_count=orbit_count,
        time_step_s=time_step_s,
        parameters=thermal,
        orbit=orbit,
        include_earth_infrared=True,
        include_albedo=False,
    )
    phase3b = simulate_orbital_eclipse(
        orbit_count=orbit_count,
        time_step_s=time_step_s,
        parameters=thermal,
        orbit=orbit,
        include_earth_infrared=True,
        include_albedo=True,
        albedo=albedo,
    )

    print("Phase 3B comparison: Earth albedo heating")
    print("Simplified single-node model result.")
    print(f"Earth Bond albedo a: {albedo.earth_bond_albedo:.2f}")
    print(f"Albedo area A_albedo: {albedo.albedo_area_m2:.4f} m^2")
    print(f"Solar absorptivity alpha: {thermal.absorptivity:.2f}")
    print(f"Peak geometry factor F_albedo(theta=0): {peak_factor:.6f}")
    print(f"Peak Q_albedo: {peak_albedo_w:.6f} W")
    print(f"Orbits: {orbit_count}")
    print(f"Time step: {time_step_s:g} s")
    print()
    _print_case("Phase 3A (Earth IR on, albedo off)", phase3a.temperature_k)
    print()
    _print_case("Phase 3B (Earth IR on, albedo on)", phase3b.temperature_k)
    print()

    a_i, a_min, a_max, a_f = _stats(phase3a.temperature_k)
    b_i, b_min, b_max, b_f = _stats(phase3b.temperature_k)
    print("Differences (Phase 3B - Phase 3A)")
    print(f"  Initial: {b_i - a_i:.6f} K")
    print(f"  Minimum: {b_min - a_min:.6f} K")
    print(f"  Maximum: {b_max - a_max:.6f} K")
    print(f"  Final:   {b_f - a_f:.6f} K")

    plot_phase3a_phase3b_comparison(
        phase3a, phase3b, output_path=output_path, show=show
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
