"""Run the Phase 1 continuous-sunlight study and save a temperature plot.

Study definition
----------------
Duration: 90 minutes of uninterrupted sunlight.
Integrator: explicit Euler with a default step of 1 second.
Environment model: solar input plus constant internal heat minus node emission.
Not included: orbital geometry, eclipse, Earth infrared, albedo, and a GUI.

The printed temperatures are Celsius. The solver uses kelvin.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap
from _bootstrap import ROOT

from satellite_thermal.parameters import Phase1Parameters
from satellite_thermal.plotting import plot_temperature_history
from satellite_thermal.simulation import simulate_continuous_sunlight
from satellite_thermal.units import kelvin_to_celsius

PHASE1_DURATION_S = 90.0 * 60.0
DEFAULT_PLOT = ROOT / "outputs" / "phase1_temperature.png"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 1 single-node satellite thermal model: "
            "90 minutes of continuous sunlight."
        )
    )
    parser.add_argument(
        "--time-step",
        type=float,
        default=1.0,
        help="Explicit Euler time step in seconds (default: 1).",
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


def run(time_step_s: float = 1.0, output_path: Path = DEFAULT_PLOT, show: bool = False) -> None:
    """Simulate the default Phase 1 case and write the temperature plot."""
    parameters = Phase1Parameters().validated()
    result = simulate_continuous_sunlight(
        duration_s=PHASE1_DURATION_S,
        time_step_s=time_step_s,
        parameters=parameters,
    )
    initial_c = kelvin_to_celsius(result.temperature_k[0])
    final_c = kelvin_to_celsius(result.temperature_k[-1])

    print("Phase 1 single-node model, continuous sunlight")
    print("Simplified single-node model result.")
    print(f"Duration: {PHASE1_DURATION_S:.0f} s ({PHASE1_DURATION_S / 60.0:.0f} min)")
    print(f"Time step: {time_step_s:g} s")
    print(f"Samples: {len(result.time_s)}")
    print(f"Initial temperature: {result.temperature_k[0]:.4f} K ({initial_c:.4f} °C)")
    print(f"Final temperature:   {result.temperature_k[-1]:.4f} K ({final_c:.4f} °C)")

    plot_temperature_history(result, output_path=output_path, show=show)
    print(f"Plot saved to: {output_path}")


def main() -> None:
    args = build_parser().parse_args()
    run(time_step_s=args.time_step, output_path=args.output, show=args.show)


if __name__ == "__main__":
    main()
