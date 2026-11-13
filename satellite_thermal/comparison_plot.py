"""Comparison plot of Phase 2 and Phase 3A orbital temperature histories.

Both runs share the same orbit and eclipse geometry. The Phase 3A curve adds
a constant absorbed Earth-infrared term. Temperatures are shown in Celsius.
Stored histories remain in kelvin.
"""

from __future__ import annotations

from pathlib import Path

from satellite_thermal.orbital_simulation import (
    OrbitalThermalResult,
    eclipse_intervals_s,
)
from satellite_thermal.units import kelvin_to_celsius


def plot_phase2_phase3a_comparison(
    phase2: OrbitalThermalResult,
    phase3a: OrbitalThermalResult,
    output_path: str | Path | None = None,
    show: bool = False,
):
    """Plot both temperature histories with shared eclipse shading.

    Returns the Matplotlib figure.
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    if phase2.time_s != phase3a.time_s:
        raise ValueError("Compared runs must share the same sample times.")
    if phase2.in_eclipse != phase3a.in_eclipse:
        raise ValueError("Compared runs must share the same eclipse flags.")

    time_min = [second / 60.0 for second in phase2.time_s]
    phase2_c = [kelvin_to_celsius(temp_k) for temp_k in phase2.temperature_k]
    phase3a_c = [kelvin_to_celsius(temp_k) for temp_k in phase3a.temperature_k]
    intervals = eclipse_intervals_s(phase2.time_s, phase2.in_eclipse)

    figure, axis = plt.subplots(figsize=(10, 5.0))
    for start_s, end_s in intervals:
        axis.axvspan(start_s / 60.0, end_s / 60.0, color="#f0c27a", alpha=0.45, zorder=0)

    axis.plot(
        time_min,
        phase2_c,
        color="#4c4c4c",
        linewidth=1.6,
        linestyle="--",
        zorder=2,
        label="Phase 2 (no Earth IR)",
    )
    axis.plot(
        time_min,
        phase3a_c,
        color="#0b6e4f",
        linewidth=1.8,
        zorder=3,
        label="Phase 3A (with Earth IR)",
    )
    axis.set_xlabel("Time (minutes)")
    axis.set_ylabel("Temperature (°C)")
    axis.set_title("Five-orbit comparison: Earth infrared heating")
    axis.grid(True, alpha=0.35, zorder=1)
    axis.legend(
        handles=[
            axis.lines[0],
            axis.lines[1],
            Patch(facecolor="#f0c27a", edgecolor="none", alpha=0.9, label="Eclipse"),
        ],
        loc="best",
    )
    upper = max(max(phase2_c), max(phase3a_c))
    lower = min(min(phase2_c), min(phase3a_c))
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
            zorder=4,
        )
    axis.text(
        0.0,
        -0.22,
        "Simplified single-node model. No albedo. Not a flight prediction.",
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


def plot_phase3a_phase3b_comparison(
    phase3a: OrbitalThermalResult,
    phase3b: OrbitalThermalResult,
    output_path: str | Path | None = None,
    show: bool = False,
):
    """Plot Phase 3A vs Phase 3B temperature histories with eclipse shading.

    Phase 3A has Earth IR on and albedo off. Phase 3B adds albedo.
    Returns the Matplotlib figure.
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    if phase3a.time_s != phase3b.time_s:
        raise ValueError("Compared runs must share the same sample times.")
    if phase3a.in_eclipse != phase3b.in_eclipse:
        raise ValueError("Compared runs must share the same eclipse flags.")

    time_min = [second / 60.0 for second in phase3a.time_s]
    phase3a_c = [kelvin_to_celsius(temp_k) for temp_k in phase3a.temperature_k]
    phase3b_c = [kelvin_to_celsius(temp_k) for temp_k in phase3b.temperature_k]
    intervals = eclipse_intervals_s(phase3a.time_s, phase3a.in_eclipse)

    figure, axis = plt.subplots(figsize=(10, 5.0))
    for start_s, end_s in intervals:
        axis.axvspan(start_s / 60.0, end_s / 60.0, color="#f0c27a", alpha=0.45, zorder=0)

    axis.plot(
        time_min,
        phase3a_c,
        color="#4c4c4c",
        linewidth=1.6,
        linestyle="--",
        zorder=2,
        label="Phase 3A (Earth IR, no albedo)",
    )
    axis.plot(
        time_min,
        phase3b_c,
        color="#1d4e89",
        linewidth=1.8,
        zorder=3,
        label="Phase 3B (Earth IR + albedo)",
    )
    axis.set_xlabel("Time (minutes)")
    axis.set_ylabel("Temperature (°C)")
    axis.set_title("Five-orbit comparison: Earth albedo heating")
    axis.grid(True, alpha=0.35, zorder=1)
    axis.legend(
        handles=[
            axis.lines[0],
            axis.lines[1],
            Patch(facecolor="#f0c27a", edgecolor="none", alpha=0.9, label="Eclipse"),
        ],
        loc="best",
    )
    upper = max(max(phase3a_c), max(phase3b_c))
    lower = min(min(phase3a_c), min(phase3b_c))
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
            zorder=4,
        )
    axis.text(
        0.0,
        -0.22,
        "Simplified single-node model. Not a flight prediction.",
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

