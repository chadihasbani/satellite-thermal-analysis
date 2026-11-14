# Checkpoint 6 verification notes

Educational single-node simulator. Numbers below are from Checkpoint 6 runs on
the integration branch; they are **not** flight measurements.

## Suite

- Automated tests: `python -m unittest discover -s tests -v`
- Checkpoint 6 measured run: **182 tests, ~95.3 s wall time, 0 failures**.
- Slowest: `test_shadow_and_eclipse_state_at_zero_sixty_seventy_five` (~31 s) —
  builds Plotly 3D figures for three beta cases. Cost is visualization
  construction, not a thermal-solver regression. Do not weaken that test solely
  for speed.
- Next slowest cluster (~7.5 s each): five independent re-runs of the legacy
  V1 A/B/C environment stack from different checkpoint test modules (intentional
  regression guards, not unexpected recomputation inside the solver).

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

Projected solar area at that sample: 0.01000 m² (nadir / β = 0°).

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

**Physical differences:** Case B removes eclipse and raises sunlit projected area
under nadir + high beta, so the bus stays much warmer. Case D nadir presents a
smaller average sunlit projected area than fixed/sun at β = 0° for this body-axis
convention. Case E applies documented screening overlays (fluxes, beta, Qin).

## Energy balance

Discrete Euler residual `|Σ Q_net Δt − m cp ΔT|` for Case A-class runs is on the
order of **10⁻⁹ J** (floating-point). Instantaneous snapshots satisfy
`Q_net = Q_solar + Q_IR + Q_alb + Q_int − Q_rad`. Solar and albedo are zero in
eclipse. This is discrete numerical consistency, not physical validation.

## Convergence (nominal 3U, 2 orbits)

Final temperatures (°C): dt 10 → −22.654; 5 → −22.644; 2 → −22.659; 1 → −22.650
(and ~−22.654 at 0.5 s in exploratory runs). Non-monotonic in dt due to eclipse
sampling; all within ~0.05 °C of the 1 s reference. Coarse dt = 30 s vs 1 s
final difference remains < 0.5 °C for the one-orbit sensitivity check.

## Legacy baselines

500 km, five orbits, dt = 1 s, legacy simplified configuration:

- Case A ≈ −12.5661 °C
- Case B ≈ −6.8313 °C
- Case C ≈ −4.5386 °C

## Release stance

See the Checkpoint 6 report in the review conversation: the project is suitable
as a **transparent educational / engineering-exploration** release after
documentation review, with known physical-model limitations clearly stated. It
is **not** flight-qualified design software.
