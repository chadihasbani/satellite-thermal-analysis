"""Run five circular orbits with geometric eclipse and save the plot.

Earth infrared and albedo are not included.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap
from _bootstrap import ROOT

from satellite_thermal.orbit import CircularOrbit, orbital_radius_m
from satellite_thermal.orbital_plot import plot_orbital_temperature
from satellite_thermal.orbital_simulation import simulate_orbital_eclipse
from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.units import kelvin_to_celsius

DEFAULT_PLOT = ROOT / "outputs" / "phase2_temperature.png"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 2 single-node model: circular 500 km orbit with "
            "geometric sunlight and eclipse."
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
        help="Where to save the temperature plot.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Open an interactive Matplotlib window after saving.",
    )
    return parser


def _minutes(seconds: float) -> float:
    return seconds / 60.0


def run(
    time_step_s: float = 1.0,
    orbit_count: int = 5,
    output_path: Path = DEFAULT_PLOT,
    show: bool = False,
) -> None:
    """Simulate the default Phase 2 case and write the temperature plot."""
    thermal = Phase1Parameters().validated()
    orbit = CircularOrbit().validated()
    result = simulate_orbital_eclipse(
        orbit_count=orbit_count,
        time_step_s=time_step_s,
        parameters=thermal,
        orbit=orbit,
    )
    minimum_k = min(result.temperature_k)
    maximum_k = max(result.temperature_k)
    final_k = result.temperature_k[-1]

    print("Phase 2 single-node model, circular orbit with geometric eclipse")
    print("Teaching result. Earth infrared and albedo are not included.")
    print(f"Altitude: {orbit.altitude_m / 1000.0:.3f} km")
    print(f"Orbital radius: {orbital_radius_m(orbit) / 1000.0:.3f} km")
    print(f"Beta angle: {orbit.beta_rad:.3f} rad")
    print(
        f"Orbital period: {result.period_s:.4f} s ({_minutes(result.period_s):.4f} min)"
    )
    print(
        "Eclipse duration per orbit: "
        f"{result.eclipse_duration_s:.4f} s ({_minutes(result.eclipse_duration_s):.4f} min)"
    )
    print(
        "Sunlight duration per orbit: "
        f"{result.sunlight_duration_s:.4f} s ({_minutes(result.sunlight_duration_s):.4f} min)"
    )
    print(f"Orbits: {result.orbit_count}")
    print(f"Time step: {result.time_step_s:g} s")
    print(f"Minimum temperature: {minimum_k:.4f} K ({kelvin_to_celsius(minimum_k):.4f} °C)")
    print(f"Maximum temperature: {maximum_k:.4f} K ({kelvin_to_celsius(maximum_k):.4f} °C)")
    print(f"Final temperature:   {final_k:.4f} K ({kelvin_to_celsius(final_k):.4f} °C)")

    plot_orbital_temperature(result, output_path=output_path, show=show)
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
