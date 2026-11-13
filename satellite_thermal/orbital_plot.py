"""Temperature plot for the Phase 2 orbit, with eclipse intervals marked.

Temperatures are displayed in degrees Celsius. The stored history remains in
kelvin. Shaded bands are the steps on which the cylindrical shadow test turned
solar heating off.
"""

from __future__ import annotations

from pathlib import Path

from satellite_thermal.orbital_simulation import (
    OrbitalThermalResult,
    eclipse_intervals_s,
)
from satellite_thermal.units import kelvin_to_celsius


def plot_orbital_temperature(
    result: OrbitalThermalResult,
    output_path: str | Path | None = None,
    show: bool = False,
):
    """Plot temperature against time and shade each eclipse.

    Returns the Matplotlib figure.
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    time_min = [second / 60.0 for second in result.time_s]
    temperature_c = [kelvin_to_celsius(temp_k) for temp_k in result.temperature_k]
    intervals = eclipse_intervals_s(result.time_s, result.in_eclipse)

    figure, axis = plt.subplots(figsize=(10, 4.8))
    for start_s, end_s in intervals:
        axis.axvspan(start_s / 60.0, end_s / 60.0, color="#f0c27a", alpha=0.55, zorder=0)
    axis.plot(time_min, temperature_c, color="#0b6e4f", linewidth=1.8, zorder=2, label="Temperature")
    axis.set_xlabel("Time (minutes)")
    axis.set_ylabel("Temperature (°C)")
    axis.set_title("Single-node temperature over five orbits (beta = 0)")
    axis.grid(True, alpha=0.35, zorder=1)
    axis.legend(
        handles=[
            axis.lines[0],
            Patch(facecolor="#f0c27a", edgecolor="none", alpha=0.9, label="Eclipse"),
        ],
        loc="best",
    )
    upper = max(temperature_c)
    lower = min(temperature_c)
    span = max(upper - lower, 1.0)
    label_y = upper - 0.06 * span
    for start_s, end_s in intervals:
        axis.text(
            0.5 * (start_s + end_s) / 60.0,
            label_y,
            "Eclipse",
            ha="center",
            va="top",
            fontsize=8,
            color="#6a4b12",
            zorder=3,
        )
    axis.text(
        0.0,
        -0.22,
        "Simplified orbit model. No Earth infrared or albedo. Not a flight prediction.",
        transform=axis.transAxes,
        fontsize=8,
        color="#444444",
    )
    figure.tight_layout()

    if output_path is not None:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(destination, dpi=150, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close(figure)

    return figure
