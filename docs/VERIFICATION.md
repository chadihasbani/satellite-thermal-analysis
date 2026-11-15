# Numerical verification summary

Educational single-node simulator. Numbers below are from integrated
Version 2.0 verification runs; they are **not** flight measurements.

## Current product scope

The Streamlit application exposes:

- **Satellite Thermal Simulation** (single run)
- **Compare Heat Sources** (A/B/C environmental stack: sunlight only → +Earth IR → +albedo)

Active GUI operations use **constant internal power** and **fixed-inertial**
enhanced solar heating (legacy fixed-area path remains for the Reference
Satellite). Attitude modes other than fixed-inertial, variable power schedules,
and Hot/Nominal/Cold screening are **not** in the current UI; numerical records
below that exercise those features are retained as **historical V2 development
evidence**.

## Suite

- Automated tests: `python -m unittest discover -s tests -v`
- Latest full local suite on the simplified product branch: **141 tests**,
  **~127 s**, 0 failures (2026-11-15 release-blocking verification).
- Slowest visualization tests build Plotly 3D figures — cost is figure
  construction, not a thermal-solver regression.

## Legacy Version 1 baselines (preserved)

500 km, five orbits, dt = 1 s, legacy simplified configuration:

- Case A (no Earth heating) ≈ **−12.5661 °C**
- Case B (+Earth IR) ≈ **−6.8313 °C**
- Case C (+Earth IR + albedo) ≈ **−4.5386 °C**

These finals remain the primary continuity check for the educational model and
for Compare Heat Sources under Reference Satellite defaults.

## Current integration checks (generic 3U-inspired, 500 km)

Active coverage in `tests/test_checkpoint6_integration.py` (simplified product):

| Check | Setup | Notes |
| --- | --- | --- |
| Case A-class | Fixed inertial, β = 0°, 3 orbits, dt = 5 s, Earth IR + albedo | Period / eclipse sampling; finite ordered temperatures |
| Case B-class | Legacy heating, β = 75° vs 0° | Above β_c ≈ 68.007° → no eclipse; warmer final than β = 0° |
| Energy identity | Discrete Euler residual | `|Σ Q_net Δt − m cp ΔT|` ~ floating-point |
| Geometry / beta | Independent rebuilds | Period, `β_c`, face areas, projected-area bounds |
| Time-step study | dt ∈ {10, 5, 2, 1} s | Finals stay within ~0.05 °C of 1 s reference (non-monotonic) |
| V1 env stack | Legacy Reference A/B/C | −12.5661 / −6.8313 / −4.5386 °C |

### Representative heat flows (Reference Satellite, sunlit sample)

At the default inspection sample these match the educational V1 stack order of
magnitude (exact GUI panel values depend on the selected time):

| Term | W (illustrative sunlit) |
| --- | --- |
| Q_solar | ≈ 8.17 |
| Q_earth_ir | ≈ 1.65 |
| Q_albedo | ≈ 2.11 |
| Q_internal | 5.00 |

### Historical Checkpoint 6 temperature metrics (°C)

The following table is retained from the pre-simplification integration pass
(nadir / pulsed power / multi-attitude / Hot–Cold). Those features are **not**
in the current GUI or active Case A/B tests; numbers are archival evidence only.

| Case | Initial | Min | Max | Final |
| --- | --- | --- | --- | --- |
| A nadir β = 0° | 20.000 | −32.420 | 20.000 | −28.995 |
| B nadir β = 75° | 20.000 | 2.234 | 20.000 | 2.240 |
| C pulsed (1 orbit) | 20.000 | −9.785 | 20.007 | −9.785 |
| D fixed inertial | 20.000 | −28.869 | 20.000 | −24.297 |
| D nadir | 20.000 | −32.420 | 20.000 | −28.995 |
| D sun-pointing | 20.000 | −28.869 | 20.000 | −24.297 |
| E Cold | 20.000 | −31.213 | 20.000 | −30.177 |
| E Nominal | 20.000 | −24.621 | 20.000 | −22.654 |
| E Hot | 20.000 | 19.815 | 21.090 | 20.727 |

## Energy balance

Discrete Euler residual `|Σ Q_net Δt − m cp ΔT|` for Case A-class runs is on the
order of **10⁻⁹ J** (floating-point). Instantaneous snapshots satisfy
`Q_net = Q_solar + Q_IR + Q_alb + Q_int − Q_rad`. Solar and albedo are zero in
eclipse. This is discrete numerical consistency, not physical validation.

## Release stance

Suitable as a **transparent educational / engineering-exploration** release with
known physical-model limitations clearly stated. **Not** flight-qualified design
software.

Internal development history for the pre-simplification integration pass was
labelled “Checkpoint 6”. The separate `CHECKPOINT6_VERIFICATION.md` file was
removed with the product simplification; the numerical evidence above and in
`tests/test_checkpoint6_integration.py` remains the record.
