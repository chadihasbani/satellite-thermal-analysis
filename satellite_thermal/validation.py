"""Input checks for the Phase 1 thermal model.

Temperatures are absolute temperatures in kelvin. Heat flows are in watts.
"""

from __future__ import annotations


def require_finite_number(name: str, value: object) -> float:
    """Return value as a finite float, or raise ValueError."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number, got {value!r}.")
    number = float(value)
    if number != number or number == float("inf") or number == float("-inf"):
        raise ValueError(f"{name} must be finite, got {value!r}.")
    return number


def require_positive(name: str, value: object) -> float:
    """Require a finite number strictly greater than zero."""
    number = require_finite_number(name, value)
    if number <= 0.0:
        raise ValueError(f"{name} must be greater than 0, got {number}.")
    return number


def require_non_negative(name: str, value: object) -> float:
    """Require a finite number greater than or equal to zero."""
    number = require_finite_number(name, value)
    if number < 0.0:
        raise ValueError(f"{name} must be greater than or equal to 0, got {number}.")
    return number


def require_fraction(name: str, value: object) -> float:
    """Require a finite surface property in the closed interval [0, 1]."""
    number = require_finite_number(name, value)
    if number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be between 0 and 1, got {number}.")
    return number
