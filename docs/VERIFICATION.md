# Numerical verification summary

Educational single-node simulator. Numbers below are from integrated
Version 2.0 verification runs; they are **not** flight measurements.

## Suite

- Automated tests: `python -m unittest discover -s tests -v`
- Latest full local suite (Version 2.0 release prep): **192 tests**, **~184 s**,
  0 failures. Pre-PDF baseline was 182 tests; PDF/report tests extend the suite.
- Slowest visualization test builds Plotly 3D figures for three beta cases —
  cost is figure construction, not a thermal-solver regression.

## Integrated Cases A–E (generic 3U-inspired, 500 km)

Shared unless noted: CDS 3U envelope geometry, enhanced model, Earth IR + albedo
on, `T0 = 20 °C`, illustrative `Qin = 5 W` constant (Case C differs).

| Case | Setup | Period (s) | Analytical eclipse (s) | Stored eclipse (s) | Notes |
| --- | --- | --- | --- | --- | --- |
| A | Nadir, β = 0°, 3 orbits, dt = 5 s | 5668.144 | 2141.523 | 2140.000 | Discrete eclipse within ~dt of analytical |
| B | Same, β = 75° | 5668.144 | 0 | 0 | Above β_c ≈ 68.007°; continuous sun |
| C | Custom pulse `[1,2)` at 100 W; 1 orbit | 5668.144 | 2141.523 | 2140.000 | Event-aware splits; +95 J vs 5 W baseline |
| D | Attitudes compared | 5668.144 | 2141.523 | 2140.000 | Nadir cooler; fixed≈sun at β = 0° (same A_proj) |
| E | Hot / Nominal / Cold, 2 orbits, dt = 10 s | — | — | — | Cold < Nominal < Hot finals |

### Representative heat flows (Case A, first sunlit sample)

| Term | W |
| --- | --- |
| Q_solar | 8.166 |
| Q_earth_ir | 1.651 |
| Q_albedo | 2.106 |
| Q_internal | 5.000 |
| Q_radiated | 52.329 |
| Q_net | −35.406 |

### Temperature metrics (°C)

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

## Legacy Version 1 baselines

500 km, five orbits, dt = 1 s, legacy simplified configuration:

- Case A ≈ −12.5661 °C
- Case B ≈ −6.8313 °C
- Case C ≈ −4.5386 °C

## Release stance

Suitable as a **transparent educational / engineering-exploration** release with
known physical-model limitations clearly stated. **Not** flight-qualified design
software.

Internal development history for this integration pass was previously labelled
“Checkpoint 6”; see [`CHECKPOINT6_VERIFICATION.md`](CHECKPOINT6_VERIFICATION.md)
for the original filename pointer.
