"""Time-dependent internal heat generation schedules.

Governing use
-------------
The single-node energy balance uses

    Q_internal = Q_internal(t)

evaluated at the start of each explicit Euler step (the same time used for
eclipse gating and solar loads). For ``periodic_high`` and ``custom_intervals``
schedules, the integrator also queries ``next_scheduled_transition_s`` so that
steps are shortened to land on known power discontinuities (event-aware
splitting). ``eclipse_reduced`` still follows the sampled eclipse flag; it does
not introduce separate eclipse-boundary events.

This module does **not** model batteries, electrical efficiency, or multi-node
equipment thermal networks.

Illustrative operating levels
-----------------------------
Default standby / nominal / high-power wattages are **illustrative modelling
assumptions (C)** for educational screening. They are not published values for
any specific commercial spacecraft.

Schedule kinds
--------------
1. ``constant`` — fixed power (default; preserves Version 1.0 when 5 W).
2. ``eclipse_reduced`` — sunlight power when sunlit; eclipse power when the
   cylindrical Earth-shadow test (including beta) reports eclipse.
3. ``periodic_high`` — within each period ``[nP, (n+1)P)``, high power on
   ``[nP, nP + high_duration)`` and base power otherwise (half-open intervals).
4. ``custom_intervals`` — half-open intervals ``[start, end)`` with an explicit
   power. Outside all intervals the baseline ``constant_power_w`` applies.

Overlaps and invalid data
-------------------------
Custom intervals must not overlap. Adjacent intervals that share an endpoint
are allowed (``[0, 10)`` and ``[10, 20)``). Overlaps, ``start >= end``,
negative times, or negative powers raise ``ValueError``.

Priority is unambiguous: for custom schedules only one interval can contain a
given time; for other kinds a single rule applies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from satellite_thermal.validation import (
    require_finite_number,
    require_non_negative,
    require_positive,
)

# Illustrative defaults (classification C) — not a manufacturer datasheet.
ILLUSTRATIVE_STANDBY_W = 1.0
ILLUSTRATIVE_NOMINAL_W = 5.0
ILLUSTRATIVE_HIGH_POWER_W = 15.0


class PowerScheduleKind(str, Enum):
    """Supported internal-power schedule kinds."""

    CONSTANT = "constant"
    ECLIPSE_REDUCED = "eclipse_reduced"
    PERIODIC_HIGH = "periodic_high"
    CUSTOM_INTERVALS = "custom_intervals"


class OperatingModeName(str, Enum):
    """Named illustrative operating levels."""

    STANDBY = "standby"
    NOMINAL = "nominal"
    HIGH_POWER = "high_power"


def parse_power_schedule_kind(value: str | PowerScheduleKind) -> PowerScheduleKind:
    if isinstance(value, PowerScheduleKind):
        return value
    try:
        return PowerScheduleKind(str(value).strip().lower())
    except ValueError as exc:
        allowed = ", ".join(kind.value for kind in PowerScheduleKind)
        raise ValueError(
            f"power_schedule_kind must be one of: {allowed}. Got {value!r}."
        ) from exc


def parse_operating_mode_name(value: str | OperatingModeName) -> OperatingModeName:
    if isinstance(value, OperatingModeName):
        return value
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in ("high", "highpower"):
        normalized = OperatingModeName.HIGH_POWER.value
    try:
        return OperatingModeName(normalized)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in OperatingModeName)
        raise ValueError(
            f"operating_mode must be one of: {allowed}. Got {value!r}."
        ) from exc


@dataclass(frozen=True)
class OperatingModePowers:
    """Illustrative power levels for named operating modes, in watts."""

    standby_w: float = ILLUSTRATIVE_STANDBY_W
    nominal_w: float = ILLUSTRATIVE_NOMINAL_W
    high_power_w: float = ILLUSTRATIVE_HIGH_POWER_W

    def validated(self) -> "OperatingModePowers":
        return OperatingModePowers(
            standby_w=require_non_negative("standby_w", self.standby_w),
            nominal_w=require_non_negative("nominal_w", self.nominal_w),
            high_power_w=require_non_negative("high_power_w", self.high_power_w),
        )

    def power_for(self, mode: str | OperatingModeName) -> float:
        settings = self.validated()
        name = parse_operating_mode_name(mode)
        if name is OperatingModeName.STANDBY:
            return settings.standby_w
        if name is OperatingModeName.NOMINAL:
            return settings.nominal_w
        return settings.high_power_w


@dataclass(frozen=True)
class PowerInterval:
    """Half-open custom power interval [start_s, end_s)."""

    start_s: float
    end_s: float
    power_w: float
    label: str = "custom"

    def validated(self) -> "PowerInterval":
        start = require_non_negative("start_s", self.start_s)
        end = require_finite_number("end_s", self.end_s)
        power = require_non_negative("power_w", self.power_w)
        if end <= start:
            raise ValueError(
                f"Power interval requires end_s > start_s, got [{start}, {end})."
            )
        label = str(self.label).strip() or "custom"
        return PowerInterval(start_s=start, end_s=end, power_w=power, label=label)

    def contains(self, time_s: float) -> bool:
        settings = self.validated()
        time = require_non_negative("time_s", time_s)
        return settings.start_s <= time < settings.end_s


@dataclass(frozen=True)
class InternalPowerSchedule:
    """Complete internal-power schedule used by the thermal integrator."""

    kind: str = PowerScheduleKind.CONSTANT.value
    constant_power_w: float = ILLUSTRATIVE_NOMINAL_W
    sunlight_power_w: float = ILLUSTRATIVE_NOMINAL_W
    eclipse_power_w: float = ILLUSTRATIVE_STANDBY_W
    base_power_w: float = ILLUSTRATIVE_NOMINAL_W
    high_power_w: float = ILLUSTRATIVE_HIGH_POWER_W
    period_s: float = 600.0
    high_duration_s: float = 120.0
    intervals: tuple[PowerInterval, ...] = ()

    def validated(self) -> "InternalPowerSchedule":
        kind = parse_power_schedule_kind(self.kind)
        constant = require_non_negative("constant_power_w", self.constant_power_w)
        sunlight = require_non_negative("sunlight_power_w", self.sunlight_power_w)
        eclipse = require_non_negative("eclipse_power_w", self.eclipse_power_w)
        base = require_non_negative("base_power_w", self.base_power_w)
        high = require_non_negative("high_power_w", self.high_power_w)
        period = require_positive("period_s", self.period_s)
        high_duration = require_non_negative("high_duration_s", self.high_duration_s)
        if high_duration > period:
            raise ValueError(
                "high_duration_s must be <= period_s for periodic_high schedules."
            )
        cleaned = tuple(interval.validated() for interval in self.intervals)
        _assert_no_overlapping_intervals(cleaned)
        return InternalPowerSchedule(
            kind=kind.value,
            constant_power_w=constant,
            sunlight_power_w=sunlight,
            eclipse_power_w=eclipse,
            base_power_w=base,
            high_power_w=high,
            period_s=period,
            high_duration_s=high_duration,
            intervals=cleaned,
        )

    def power_w_at(self, time_s: float, in_eclipse: bool) -> float:
        """Internal heat generation at time_s, in watts."""
        settings = self.validated()
        time = require_non_negative("time_s", time_s)
        if not isinstance(in_eclipse, bool):
            raise ValueError(f"in_eclipse must be a bool, got {in_eclipse!r}.")
        kind = parse_power_schedule_kind(settings.kind)

        if kind is PowerScheduleKind.CONSTANT:
            return settings.constant_power_w

        if kind is PowerScheduleKind.ECLIPSE_REDUCED:
            return (
                settings.eclipse_power_w
                if in_eclipse
                else settings.sunlight_power_w
            )

        if kind is PowerScheduleKind.PERIODIC_HIGH:
            phase = time % settings.period_s
            if phase < settings.high_duration_s:
                return settings.high_power_w
            return settings.base_power_w

        # CUSTOM_INTERVALS
        for interval in settings.intervals:
            if interval.contains(time):
                return interval.power_w
        return settings.constant_power_w

    def state_label_at(self, time_s: float, in_eclipse: bool) -> str:
        """Short label for GUI / exports describing the active power state."""
        settings = self.validated()
        time = require_non_negative("time_s", time_s)
        if not isinstance(in_eclipse, bool):
            raise ValueError(f"in_eclipse must be a bool, got {in_eclipse!r}.")
        kind = parse_power_schedule_kind(settings.kind)

        if kind is PowerScheduleKind.CONSTANT:
            return "constant"

        if kind is PowerScheduleKind.ECLIPSE_REDUCED:
            return "eclipse" if in_eclipse else "sunlight"

        if kind is PowerScheduleKind.PERIODIC_HIGH:
            phase = time % settings.period_s
            return "periodic_high" if phase < settings.high_duration_s else "periodic_base"

        for interval in settings.intervals:
            if interval.contains(time):
                return interval.label
        return "baseline"

    def next_scheduled_transition_s(
        self,
        time_s: float,
        until_s: float | None = None,
    ) -> float | None:
        """Next known internal-power discontinuity strictly after ``time_s``.

        Returns
        -------
        float or None
            The next transition time, or ``None`` if there is no schedule-driven
            event before ``until_s`` (when given).

        Notes
        -----
        Applies to ``periodic_high`` and ``custom_intervals`` only.
        ``constant`` has no transitions. ``eclipse_reduced`` depends on the
        orbital eclipse test and does **not** report eclipse-boundary events
        here; those remain sampled with the integrator's orbital time step.
        """
        settings = self.validated()
        time = require_non_negative("time_s", time_s)
        horizon = None
        if until_s is not None:
            horizon = require_finite_number("until_s", until_s)
            if horizon <= time:
                return None

        kind = parse_power_schedule_kind(settings.kind)
        if kind in (PowerScheduleKind.CONSTANT, PowerScheduleKind.ECLIPSE_REDUCED):
            return None

        if kind is PowerScheduleKind.PERIODIC_HIGH:
            return _next_periodic_transition_s(
                time_s=time,
                period_s=settings.period_s,
                high_duration_s=settings.high_duration_s,
                until_s=horizon,
            )

        candidates: list[float] = []
        for interval in settings.intervals:
            for edge in (interval.start_s, interval.end_s):
                if edge > time and (horizon is None or edge < horizon):
                    candidates.append(edge)
        if not candidates:
            return None
        return min(candidates)


def _next_periodic_transition_s(
    time_s: float,
    period_s: float,
    high_duration_s: float,
    until_s: float | None,
) -> float | None:
    """Next periodic high/base switch strictly after time_s."""
    # No discontinuity if always base or always high.
    if high_duration_s <= 0.0 or high_duration_s >= period_s:
        return None

    period_start = math.floor(time_s / period_s) * period_s
    candidates: list[float] = []
    # Inspect the current period and the next two (wraparound / near edges).
    for offset in (0, 1, 2):
        start_high = period_start + offset * period_s
        end_high = start_high + high_duration_s
        if start_high > time_s:
            candidates.append(start_high)
        if end_high > time_s:
            candidates.append(end_high)

    if until_s is not None:
        candidates = [value for value in candidates if value < until_s]
    if not candidates:
        return None
    return min(candidates)


def constant_power_schedule(power_w: float) -> InternalPowerSchedule:
    """Backward-compatible constant schedule."""
    return InternalPowerSchedule(
        kind=PowerScheduleKind.CONSTANT.value,
        constant_power_w=require_non_negative("power_w", power_w),
    ).validated()


def _assert_no_overlapping_intervals(intervals: tuple[PowerInterval, ...]) -> None:
    ordered = sorted(intervals, key=lambda item: (item.start_s, item.end_s))
    previous_end = None
    previous = None
    for interval in ordered:
        if previous_end is not None and interval.start_s < previous_end:
            raise ValueError(
                "Custom power intervals must not overlap. "
                f"Conflict between [{previous.start_s}, {previous.end_s}) and "
                f"[{interval.start_s}, {interval.end_s})."
            )
        previous_end = interval.end_s
        previous = interval
