"""Multi-curve temperature plots for Phase 4 sensitivity groups."""

from __future__ import annotations

from pathlib import Path

from satellite_thermal.orbital_simulation import eclipse_intervals_s
from satellite_thermal.sensitivity import SensitivityMetrics
from satellite_thermal.units import kelvin_to_celsius


def plot_sensitivity_group(
    metrics: tuple[SensitivityMetrics, ...],
    title: str,
    output_path: str | Path | None = None,
    show: bool = False,
):
    """Plot temperature histories for baseline + one parameter group.

    Returns the Matplotlib figure.
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    if len(metrics) < 2:
        raise ValueError("A sensitivity group plot needs baseline plus at least one case.")
    baseline = metrics[0]
    for item in metrics[1:]:
        if item.result.time_s != baseline.result.time_s:
            # Altitude changes the period, so sample times differ. Plot each
            # history on its own time axis in minutes anyway.
            pass

    colors = ["#4c4c4c", "#0b6e4f", "#1d4e89", "#b35c00"]
    styles = ["--", "-", "-.", ":"]

    figure, axis = plt.subplots(figsize=(10, 5.0))
    intervals = eclipse_intervals_s(
        baseline.result.time_s, baseline.result.in_eclipse
    )
    for start_s, end_s in intervals:
        axis.axvspan(
            start_s / 60.0,
            end_s / 60.0,
            color="#f0c27a",
            alpha=0.35,
            zorder=0,
        )

    for index, item in enumerate(metrics):
        time_min = [second / 60.0 for second in item.result.time_s]
        temp_c = [kelvin_to_celsius(temp_k) for temp_k in item.result.temperature_k]
        axis.plot(
            time_min,
            temp_c,
            color=colors[index % len(colors)],
            linestyle=styles[index % len(styles)],
            linewidth=1.7 if index else 1.5,
            zorder=2 + index,
            label=item.label,
        )

    axis.set_xlabel("Time (minutes)")
    axis.set_ylabel("Temperature (°C)")
    axis.set_title(title)
    axis.grid(True, alpha=0.35, zorder=1)
    handles = list(axis.lines) + [
        Patch(facecolor="#f0c27a", edgecolor="none", alpha=0.9, label="Eclipse (baseline)")
    ]
    axis.legend(handles=handles, loc="best", fontsize=8)
    axis.text(
        0.0,
        -0.22,
        "Sensitivity of the single-node model. Not experimental validation.",
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
