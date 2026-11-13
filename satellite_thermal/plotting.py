"""Matplotlib display of a Phase 1 temperature history.

The curve is a numerical result of the simplified energy balance. It is drawn
in degrees Celsius for readability. Internal data remain in kelvin.
"""

from __future__ import annotations

from pathlib import Path

from satellite_thermal.simulation import SimulationResult
from satellite_thermal.units import kelvin_to_celsius


def plot_temperature_history(
    result: SimulationResult,
    output_path: str | Path | None = None,
    show: bool = False,
):
    """Plot temperature against time and optionally save the figure.

    Time is shown in minutes. Temperature is shown in degrees Celsius.
    Returns the Matplotlib figure.
    """
    import matplotlib.pyplot as plt

    time_min = [second / 60.0 for second in result.time_s]
    temperature_c = [kelvin_to_celsius(temp_k) for temp_k in result.temperature_k]

    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.plot(time_min, temperature_c, color="#0b6e4f", linewidth=2.0)
    axis.set_xlabel("Time (minutes)")
    axis.set_ylabel("Temperature (°C)")
    axis.set_title("Single-node temperature in continuous sunlight")
    axis.grid(True, alpha=0.35)
    axis.text(
        0.0,
        -0.22,
        "Simplified single-node model.",
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
