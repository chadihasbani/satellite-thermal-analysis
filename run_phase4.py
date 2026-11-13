"""Run Phase 4 one-at-a-time sensitivity studies and save comparison plots.

Baseline is Phase 3B: Earth IR + albedo on the default 500 km orbit.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from satellite_thermal.sensitivity import (
    cases_in_group,
    run_sensitivity_study,
)
from satellite_thermal.sensitivity_plot import plot_sensitivity_group
from satellite_thermal.units import kelvin_to_celsius

OUTPUT_DIR = Path("outputs")
PLOT_GROUPS = (
    ("absorptivity", "Absorptivity sensitivity", "phase4_absorptivity.png"),
    ("emissivity", "Emissivity sensitivity (Kirchhoff alpha_ir = epsilon)", "phase4_emissivity.png"),
    ("internal_power", "Internal power sensitivity", "phase4_internal_power.png"),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 4: one-at-a-time parameter sensitivity around the "
            "Phase 3B baseline."
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
        "--show",
        action="store_true",
        help="Open interactive Matplotlib windows after saving plots.",
    )
    return parser


def _print_table(metrics) -> None:
    print(
        f"{'Case':<42} {'Tmin C':>9} {'Tmax C':>9} {'Tfinal C':>10} "
        f"{'dTmin K':>9} {'dTfinal K':>10}"
    )
    print("-" * 94)
    for item in metrics:
        print(
            f"{item.label:<42} "
            f"{kelvin_to_celsius(item.minimum_k):9.3f} "
            f"{kelvin_to_celsius(item.maximum_k):9.3f} "
            f"{kelvin_to_celsius(item.final_k):10.3f} "
            f"{item.delta_minimum_k:9.3f} "
            f"{item.delta_final_k:10.3f}"
        )


def run(time_step_s: float = 1.0, orbit_count: int = 5, show: bool = False) -> None:
    """Execute the sensitivity study, print tables, and write plots."""
    print("Phase 4 parameter sensitivity")
    print("Baseline: Phase 3B (Earth IR + albedo). Teaching model only.")
    print(f"Orbits: {orbit_count}")
    print(f"Time step: {time_step_s:g} s")
    print()

    metrics = run_sensitivity_study(
        orbit_count=orbit_count,
        time_step_s=time_step_s,
    )
    _print_table(metrics)
    print()

    ranked = sorted(
        [item for item in metrics if item.case_id != "baseline"],
        key=lambda item: abs(item.delta_final_k),
        reverse=True,
    )
    print("Largest |final temperature change| versus baseline")
    for item in ranked[:5]:
        print(
            f"  {item.label}: {item.delta_final_k:+.3f} K "
            f"(min {item.delta_minimum_k:+.3f} K)"
        )
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for group, title, filename in PLOT_GROUPS:
        group_metrics = cases_in_group(metrics, group)
        path = OUTPUT_DIR / filename
        plot_sensitivity_group(
            group_metrics,
            title=title,
            output_path=path,
            show=show,
        )
        print(f"Plot saved to: {path}")


def main() -> None:
    args = build_parser().parse_args()
    run(time_step_s=args.time_step, orbit_count=args.orbits, show=args.show)


if __name__ == "__main__":
    main()
