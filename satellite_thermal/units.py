"""Display-unit conversions.

The solver stores and advances temperature in kelvin. Celsius is only for
printed values and plot labels.
"""

from __future__ import annotations

from satellite_thermal.validation import require_finite_number


def kelvin_to_celsius(temperature_k: float) -> float:
    """Convert an absolute temperature in kelvin to degrees Celsius."""
    temperature = require_finite_number("temperature_k", temperature_k)
    return temperature - 273.15
