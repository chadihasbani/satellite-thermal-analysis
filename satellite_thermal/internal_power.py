"""Constant internal heat generation for the single-node energy balance.

Governing use
-------------
The energy balance uses a fixed onboard dissipation

    Q_internal = constant_power_w

evaluated at the start of each explicit Euler step (same time as eclipse
gating and solar loads). Variable schedules (eclipse-reduced, periodic, and
custom intervals) are not supported in this simplified simulator.

Default 5 W matches the Version 1.0 educational reference case.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from satellite_thermal.validation import require_non_negative

# Illustrative educational default (not a manufacturer datasheet).
ILLUSTRATIVE_NOMINAL_W = 5.0


class PowerScheduleKind(str, Enum):
    """Supported internal-power schedule kinds (constant only)."""

    CONSTANT = "constant"


def parse_power_schedule_kind(value: str | PowerScheduleKind) -> PowerScheduleKind:
    if isinstance(value, PowerScheduleKind):
        return value
    normalized = str(value).strip().lower()
    if normalized != PowerScheduleKind.CONSTANT.value:
        raise ValueError(
            "power_schedule_kind must be 'constant' in this simplified simulator. "
            f"Got {value!r}."
        )
    return PowerScheduleKind.CONSTANT


@dataclass(frozen=True)
class InternalPowerSchedule:
    """Constant internal-power schedule used by the thermal integrator."""

    kind: str = PowerScheduleKind.CONSTANT.value
    constant_power_w: float = ILLUSTRATIVE_NOMINAL_W

    def validated(self) -> "InternalPowerSchedule":
        parse_power_schedule_kind(self.kind)
        constant = require_non_negative("constant_power_w", self.constant_power_w)
        return InternalPowerSchedule(
            kind=PowerScheduleKind.CONSTANT.value,
            constant_power_w=constant,
        )

    def power_w_at(self, time_s: float, in_eclipse: bool) -> float:
        """Internal heat generation at time_s, in watts."""
        del time_s, in_eclipse
        return self.validated().constant_power_w

    def state_label_at(self, time_s: float, in_eclipse: bool) -> str:
        """Short label for GUI / exports describing the active power state."""
        del time_s, in_eclipse
        self.validated()
        return "constant"

    def next_scheduled_transition_s(
        self,
        time_s: float,
        until_s: float | None = None,
    ) -> float | None:
        """Constant power has no schedule-driven discontinuities."""
        del time_s, until_s
        self.validated()
        return None


def constant_power_schedule(power_w: float) -> InternalPowerSchedule:
    """Build a validated constant internal-power schedule."""
    return InternalPowerSchedule(
        kind=PowerScheduleKind.CONSTANT.value,
        constant_power_w=require_non_negative("power_w", power_w),
    ).validated()
