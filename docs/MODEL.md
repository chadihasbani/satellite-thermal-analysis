# Model details

Detailed equations, assumptions, and phase-by-phase notes for the satellite
thermal analysis project. For a short overview and how to run the app, see
the root [`README.md`](../README.md).

Phase 1 is the lumped energy balance in continuous sunlight. Phase 2 keeps
that balance and adds a circular low-Earth orbit. Direct solar heating is
turned off only while a cylindrical Earth-shadow test says the satellite is
in eclipse. Phase 3A optionally adds simplified Earth infrared heating.
Phase 3B optionally adds angle-dependent Earth albedo. Phase 4 studies
parameter sensitivity around the Phase 3B baseline. Phase 5 adds the
Streamlit GUI with comparison modes, synchronized 3D orbit visualization,
and live heat-flow diagnostics.

## Phase 1 — continuous sunlight

The node energy balance is

```text
m * cp * dT/dt = Q_solar + Q_internal - Q_radiated
```

with

```text
Q_solar    = alpha * A_projected * S
Q_radiated = epsilon * sigma * A_radiating * T**4
```

`T` is the node temperature in kelvin. Celsius appears only in printed output
and on the plot.

## Units

| Symbol | Name | Unit | Phase 1 value |
| --- | --- | --- | --- |
| `m` | Mass | kg | 5 |
| `cp` | Specific heat | J / (kg·K) | 900 |
| `T(0)` | Initial temperature | K | 293.15 (20 °C) |
| `S` | Solar flux | W / m² | 1361 |
| `alpha` | Solar absorptivity | — | 0.60 |
| `epsilon` | Infrared emissivity | — | 0.80 |
| `A_projected` | Sun-facing projected area | m² | 0.01 |
| `A_radiating` | Emitting area | m² | 0.06 |
| `Q_internal` | Internal heat | W | 5 |
| `sigma` | Stefan-Boltzmann constant | W / (m²·K⁴) | 5.670374419e-8 |

`Q_solar`, `Q_radiated`, and `Q_internal` are in watts. `dT/dt` is in K/s.

## Assumptions

- One isothermal node. There is no temperature gradient inside the satellite.
- Properties, areas, solar flux, and internal heat are constant.
- The run is 90 minutes of uninterrupted sunlight. There is no eclipse.
- `Q_radiated` is emission only. Because the specified equation has no
  environment temperature, that term is emission to a 0 K sink.
- Earth infrared, albedo, planetary heating, and view factors are not modeled.
- Attitude is fixed, so the projected area does not change.
- The time march is explicit Euler. The default step is 1 second. If the
  duration is not an integer multiple of the step, the last step is shortened
  so the simulation ends at the requested time.
- Explicit Euler is a first-order method. A 1-second step is small
  relative to this node's thermal response, but the result is still a numerical
  approximation of this simplified equation.

## Layout

See the root [`README.md`](../README.md) for the current folder map. CLI study
runners live under `scripts/`. Detailed package modules remain in
`satellite_thermal/`.

## Run

```text
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/run_phase1.py
python -m streamlit run app.py
```

CLI scripts live under `scripts/` and write plots to `outputs/`. GUI defaults
match the default reference case (Earth IR + albedo on). The default interactive
time step is 5 s (use 1 s to match CLI studies).

## Verification

These checks use the same parameters, heat-rate functions, and explicit Euler
solver as the 90-minute study. No orbital geometry, eclipse, or Earth infrared
term is added. Passing them shows that the numerical model is consistent with
its own equation. It still does not predict an actual satellite temperature.

### Analytical equilibrium

Set `dT/dt = 0`:

```text
T_eq = ((Q_solar + Q_internal) / (epsilon * sigma * A_radiating)) ** (1/4)
```

With `Q_solar = 0.60 * 0.01 * 1361 = 8.166 W` and `Q_internal = 5 W`,

```text
T_eq = (13.166 / (0.80 * 5.670374419e-8 * 0.06)) ** 0.25
     = 263.724343 K
     = -9.425657 °C
```

That rounds to the expected 263.72 K (-9.43 °C). At this temperature the
automated test checks two steady-state conditions: net heat
`Q_solar + Q_internal - Q_radiated` is 0 W within `1e-9 W`, and `dT/dt` is
0 K/s within `1e-12 K/s`.

### Long constant-sunlight run

The radiative time constant used only to pick a duration is

```text
tau = m * cp / (4 * epsilon * sigma * A_radiating * T_eq**3)
    = 22534.550 s
```

The solver then integrates the original `T**4` balance, not this linear
approximation, for `12 * tau = 270414.601 s` with a 10 s Euler step.

| Quantity | Value |
| --- | --- |
| Final temperature | 263.724497 K |
| `T_final - T_eq` | `1.537e-4` K |

The 90-minute Phase 1 result stays near 286.03 K because 5400 s is only about
0.24 time constants. That run is a transient, not a steady state.

### Time-step convergence

Explicit Euler was repeated for 5400 s at `dt = 10, 1, 0.5, 0.1` s. The
difference is `T(dt) - T(0.1 s)`.

| dt (s) | Final temperature (K) | Difference from 0.1 s (K) |
| --- | --- | --- |
| 10 | 286.02939724 | −1.761e-3 |
| 1 | 286.03099799 | −1.600e-4 |
| 0.5 | 286.03108689 | −7.112e-5 |
| 0.1 | 286.03115801 | 0 |

Each smaller step lands closer to the 0.1 s result. The default 1 s step
differs from 0.1 s by about 0.00016 K over this window, which is far smaller
than the 22 K still remaining before equilibrium.

### Assumptions and limitations

- Sunlight, areas, properties, and internal heat stay constant, as in Phase 1.
- `T_eq` is the steady state of emission to a 0 K sink. Earth infrared and
  albedo would change that temperature.
- The linearized time constant selects the long-run length. It is not part of
  the integrator.
- Explicit Euler has the same steady state as the differential equation,
  because the update stops when `dT/dt` is zero. Reaching `T_eq` checks the
  transient march; it does not add new physics.
- The 0.1 s history is a numerical reference for the step study, not a
  closed-form transient solution.
- Step-size differences are small here because every tested `dt` is much
  shorter than the 22535 s time constant. A stiffer model, or a much larger
  step, would need its own check.
- The existing 90-minute plot and `python scripts/run_phase1.py` behavior are unchanged.

## Phase 2 — circular orbit and eclipse

Phase 2 does not change the Phase 1 mass, areas, optical properties, solar
flux, internal heat, or continuous-sunlight solver. It only decides whether
the existing solar term sees `S = 1361 W/m²` or `S = 0`.

### Orbital geometry

The satellite is in a circular orbit at 500 km altitude. Earth is a sphere of
radius 6371 km, so the geocentric radius is

```text
r = R_earth + altitude = 6,871,000 m
```

The orbit lies in the XY plane. The Sun direction is fixed in that inertial
frame for the whole run. Beta is the angle between the Sun and the orbital
plane:

```text
s = (cos(beta), 0, sin(beta))
```

The Version 1.0 / default GUI case uses `beta = 0`, so the Sun is `+X` and
lies in the orbital plane. The GUI now allows other beta values; the same
Sun-vector and cylindrical-shadow definitions apply. Position angle `theta`
is measured from the sunward axis. The run starts at `theta = 0`, which is
the sun-facing side, above the subsolar point when beta = 0:

```text
theta(t) = 2 * pi * t / T_orbit
r_vec = r * (cos(theta), sin(theta), 0)
```

### Equations and units

```text
T_orbit = 2 * pi * sqrt(r**3 / mu)
mu = 3.986004418e14 m³/s²
```

`T_orbit` is in seconds. With these inputs it is **5668.1444 s (94.4691 min)**.
The period does not depend on beta.

Eclipse is not a stored number of minutes. A position is in shadow when it is
on the night side of the terminator plane and inside a cylinder of radius
`R_earth` extending anti-sunward:

```text
r_vec · s_hat < 0
|r_vec × s_hat| <= R_earth
```

With the frame above,

```text
|r_vec × s| = r * sqrt(sin²(beta) + sin²(theta) * cos²(beta))
```

At the anti-sun point (`theta = pi`) the perpendicular distance to the umbra
axis is `r |sin(beta)|`. Eclipse is therefore possible only when

```text
|beta| <= beta_critical = asin(R_earth / r) ≈ 68.007° at 500 km
```

**Classification:** derived geometric result (D) from the cylindrical-shadow
definition; not `acos(R_earth / r)` (that complementary angle is ≈ 21.99° and
is not the critical beta). For authoritative thermal-engineering discussion of
beta and cylindrical-umbra eclipse, see Rickman, TFAWS 2023 *Introduction to
On-Orbit Thermal Environments* (cylindrical-shadow simplification stated;
eclipse onset from the projected-radius condition). The closed-form duration
below is this project's derivation from the same cylinder test implemented in
code.

For `|beta| < beta_critical`,

```text
kappa = sqrt( ((R_earth/r)² - sin²(beta)) / cos²(beta) )
t_eclipse = (T_orbit / pi) * asin(kappa)
```

At `|beta| = beta_critical` the orbit is tangent to the cylinder at one
anti-sun point (measure-zero contact). Analytical duration is reported as 0.
The discrete test still counts that tangent sample because `<=` includes the
boundary. For `|beta| > beta_critical` there is continuous sunlight.

At beta = 0 this reduces to

```text
t_eclipse = T_orbit * asin(R_earth / r) / pi = 2141.523 s (35.692 min)
```

The thermal run samples that same test. With a 1 s step, a step is eclipse
when the test is true at the start of the step. That sampling gives

| Quantity | Value |
| --- | --- |
| Orbital period | 5668.1444 s (94.4691 min) |
| Eclipse per orbit (β = 0°) | 2141.0000 s (35.6833 min) |
| Sunlight per orbit (β = 0°) | 3527.1444 s (58.7857 min) |

The 0.523 s difference from the closed-form eclipse is the 1 s sampling of
the entry and exit. Eclipse plus sunlight equals one period.

### Beta verification table (500 km, dt = 1 s)

| β (°) | Analytical eclipse (min) | Numerical eclipse (min) | Notes |
| --- | --- | --- | --- |
| 0 | 35.692 | 35.683 | V1 reference |
| ±30 | 33.788 | 33.783 | ±β identical |
| 60 | 21.779 | 21.783 | shorter eclipse |
| 68 | 0.746 | 0.750 | just below critical ≈ 68.007° |
| 75 | 0.000 | 0.000 | continuous sunlight |

### Thermal coupling

The energy balance is unchanged:

```text
m * cp * dT/dt = Q_solar + Q_internal - Q_radiated
Q_solar = alpha * A_projected * S
```

`S` is 1361 W/m² in sunlight and 0 in eclipse, so `Q_solar` is 0 in eclipse.
`Q_internal` stays 5 W. Emission is still `epsilon * sigma * A_radiating * T**4`
to a 0 K sink. Earth infrared and albedo are not added. The march is explicit
Euler, using the sunlight state at the beginning of each step. The default run
is five complete orbits at a 1 s step.

### Five-orbit result

| Quantity | Value |
| --- | --- |
| Minimum temperature | 260.3333 K (-12.8167 °C) |
| Maximum temperature | 293.1500 K (20.0000 °C) |
| Final temperature | 260.5839 K (-12.5661 °C) |

The maximum is the initial temperature. The node cools in sunlight because
emission still exceeds absorbed solar power plus internal heat, and it cools
faster in eclipse because the 8.166 W solar term is removed. The plot is
`outputs/phase2_temperature.png`. Eclipse intervals are shaded and labelled.
This is a simplified transient model result, not a flight prediction.

### Assumptions and limitations

- The orbit is circular. Altitude and beta are constant over a run; the Sun
  direction is fixed in the simulation inertial frame.
- Earth is a smooth sphere. There is no atmosphere, refraction, or penumbra,
  so the shadow edge is sharp.
- Beta = 0 gives the longest eclipse for this altitude. Eclipse shortens as
  `|beta|` increases and vanishes for `|beta| >= asin(R_earth / r)`.
- **Beta changes eclipse exposure (and Sun direction in the 3D view).** It does
  **not** yet change the solar projected area. Direct solar heating still uses
  the fixed input `A_projected` whenever the satellite is sunlit. Orientation-
  dependent face solar absorption is reserved for Checkpoint 2 / Version 2.0
  enhanced mode.
- The satellite is still one isothermal node.
- Eclipse duration reported by the 1 s run is the sampled shadow test, so it
  can differ from the closed-form duration by about one step.
- Earth IR remains a constant effective-area load; albedo still uses the
  in-plane angle factor. Variable beta does not yet make planetary heating
  attitude- or beta-dependent beyond the shared eclipse gate for albedo.
- Phase 2 itself still leaves Earth infrared off. Phase 3A adds that load
  optionally. Albedo remains reserved for a later phase.
- The Phase 1 continuous-sunlight case remains `python scripts/run_phase1.py`.

## Phase 3A — simplified Earth infrared heating

Phase 3A keeps the Phase 2 orbit, eclipse geometry, and thermal parameters.
It only turns on an optional absorbed Earth-infrared term. Albedo, multiple
nodes, and a GUI are not included.

### Equations and units

The energy balance becomes

```text
m * cp * dT/dt = Q_solar + Q_internal + Q_earth_ir - Q_radiated
```

with

```text
Q_earth_ir = alpha_ir * A_earth * F_earth * E_olr
F_earth    = (R_earth / r_orbit)^2
```

| Symbol | Name | Unit | Phase 3A value |
| --- | --- | --- | --- |
| `E_olr` | Illustrative TOA outgoing longwave radiation | W/m² | 240 |
| `F_earth` | Nadir-facing flat-plate view factor to Earth | — | 0.859756 |
| `A_earth` | Effective Earth-facing area | m² | 0.01 |
| `alpha_ir` | Infrared absorptivity | — | 0.80 (= ε) |
| `Q_earth_ir` | Absorbed Earth IR | W | 1.650732 |

`E_olr` is an illustrative global-mean flux near the top of the atmosphere. It is
not the irradiance on the spacecraft until `F_earth` and `A_earth` convert it.
`alpha_ir` defaults to the existing infrared emissivity under Kirchhoff's law
for a gray surface. `A_earth = 0.01 m²` is an effective nadir-facing area at
the same scale as the existing projected area (one face of a ~0.1 m class
body). `A_radiating = 0.06 m²` still governs emission to space.

### Relation to radiation-to-space

`Q_radiated = epsilon * sigma * A_radiating * T**4` remains emission toward a
0 K sink. Phase 3A does **not** replace that term with a coupled Earth-spacecraft
radiosity exchange. Surfaces that see Earth are not given a reduced space view
factor, and Earth is not inserted as `sigma T_earth**4` in the energy balance.
Adding `Q_earth_ir` separately is a common modelling decomposition. It is
physically useful for comparing load magnitude, but it is not an exact
spacecraft thermal model.

### Availability in sunlight and eclipse

`Q_earth_ir` is constant on the circular 500 km orbit and is applied in both
sunlight and eclipse. Direct solar heating is still zero only in eclipse.
`include_earth_infrared=False` remains the default in
`simulate_orbital_eclipse`, so `python scripts/run_phase2.py` and the Phase 2 tests
keep their previous temperatures.

### Five-orbit comparison

| Case | Initial | Minimum | Maximum | Final |
| --- | --- | --- | --- | --- |
| Phase 2 (Earth IR off) | 293.1500 K (20.0000 °C) | 260.3333 K (-12.8167 °C) | 293.1500 K (20.0000 °C) | 260.5839 K (-12.5661 °C) |
| Phase 3A (Earth IR on) | 293.1500 K (20.0000 °C) | 265.8598 K (-7.2902 °C) | 293.1500 K (20.0000 °C) | 266.3187 K (-6.8313 °C) |
| Difference (3A - 2) | 0 K | +5.5265 K | 0 K | +5.7348 K |

The ~1.65 W Earth-IR load slows cooling, especially in eclipse where solar
heating is already zero. Both cases still cool over five orbits because
emission remains larger than the total heat input. The comparison plot is
`outputs/phase3a_earth_ir_comparison.png`.

### Assumptions and limitations

- `E_olr = 240 W/m²` is illustrative. Real outgoing longwave radiation varies
  with latitude, weather, and day/night Earth IR; none of that is modeled.
- `F_earth = (R/r)^2` is the nadir-facing flat-plate factor for a sphere. It
  does not account for attitude motion or self-shadowing.
- `A_earth` is an assumed effective area, not a multi-surface CAD projection.
- Emission still uses the full radiating area to a 0 K sink. A higher-fidelity
  model would split space and Earth view factors.
- Phase 3A itself still leaves albedo off. Phase 3B adds that load optionally.
  Multiple thermal nodes and a GUI are excluded.
- Phase 1 and Phase 2 defaults, plots, and verification methods are preserved.

## Phase 3B — Earth albedo (reflected sunlight)

Phase 3B keeps the Phase 2 orbit/eclipse model and the Phase 3A Earth-IR term.
It adds an optional albedo load that uses **solar absorptivity**, not infrared
emissivity.

### Equations and units

```text
m * cp * dT/dt = Q_solar + Q_internal + Q_earth_ir + Q_albedo - Q_radiated

Q_albedo = alpha * A_albedo * F_albedo * a * S
F_albedo = F_earth * max(cos(theta), 0)
F_earth  = (R_earth / r_orbit)^2
```

| Symbol | Name | Unit | Phase 3B value |
| --- | --- | --- | --- |
| `a` | Earth Bond albedo | — | 0.30 |
| `alpha` | Solar absorptivity | — | 0.60 |
| `A_albedo` | Effective albedo area | m² | 0.01 |
| `S` | Solar constant | W/m² | 1361 |
| `F_earth` | Earth view factor | — | 0.859756 |
| `F_albedo(theta=0)` | Peak albedo geometry factor | — | 0.859756 |
| `Q_albedo` peak | Absorbed albedo at subsolar point | W | 2.106231 |

`theta` is the orbital angle from the sunward axis. The cosine factor is a
teaching approximation: reflected sunlight is strongest over the day side and
is zero over the night side. If the cylindrical shadow test says the satellite
is in eclipse, `Q_albedo = 0`.

### Why albedo differs from Earth IR

| Load | Spectrum | Absorptivity | In eclipse? |
| --- | --- | --- | --- |
| Direct solar | Solar | `alpha = 0.60` | No (forced to 0) |
| Albedo | Solar (reflected) | `alpha = 0.60` | No (forced to 0) |
| Earth IR | Infrared | `alpha_ir = epsilon = 0.80` | Yes (constant) |

### Five-orbit comparison

Both cases keep Earth IR on; only albedo changes.

| Case | Initial | Minimum | Maximum | Final |
| --- | --- | --- | --- | --- |
| Phase 3A (IR on, albedo off) | 293.1500 K (20.0000 °C) | 265.8598 K (-7.2902 °C) | 293.1500 K (20.0000 °C) | 266.3187 K (-6.8313 °C) |
| Phase 3B (IR on, albedo on) | 293.1500 K (20.0000 °C) | 267.8996 K (-5.2504 °C) | 293.1500 K (20.0000 °C) | 268.6114 K (-4.5386 °C) |
| Difference (3B - 3A) | 0 K | +2.0398 K | 0 K | +2.2927 K |

Albedo warms the day side, so the minimum and final temperatures rise by about
2 K over five orbits. The maximum stays at the shared initial 20 °C because
neither case heats above the start. The comparison plot is
`outputs/phase3b_albedo_comparison.png`.

### Assumptions and limitations

- Bond albedo `a = 0.30` is a common global-mean illustrative value, not a local
  cloudy-Earth map.
- `F_albedo = F_earth * max(cos(theta), 0)` is simplified. Real albedo models
  use more detailed reflectance and attitude.
- Albedo uses the same effective area scale as the other projected loads.
- Defaults keep albedo off, so Phases 1, 2, and 3A remain unchanged when their
  previous flags are used.

## Phase 4 — parameter sensitivity

Phase 4 asks which assumptions move the predicted temperature the most. The
baseline is Phase 3B: five orbits with Earth IR and albedo enabled. Each case
changes one input. Emissivity cases also update `alpha_ir` so Kirchhoff's law
stays consistent (`alpha_ir = epsilon`).

This is a sensitivity study of the single-node model. It is **not** experimental
validation.

### Method

| Group | Perturbations |
| --- | --- |
| Solar absorptivity | 0.40, 0.60 (baseline), 0.80 |
| Emissivity / IR absorptivity | 0.60, 0.80, 1.00 |
| Internal power | 0, 5, 10 W |
| Mass (capacitance) | 0.5x, 1x, 2x |
| Radiating area | 0.04, 0.06, 0.08 m² |
| Altitude | 400, 500, 600 km |

### Five-orbit results (dt = 1 s)

| Case | Tmin (°C) | Tfinal (°C) | ΔTfinal (K) |
| --- | --- | --- | --- |
| Baseline (Phase 3B) | -5.250 | -4.539 | 0 |
| alpha = 0.40 | -11.244 | -11.151 | -6.612 |
| alpha = 0.80 | 0.474 | 1.878 | +6.417 |
| epsilon = alpha_ir = 0.60 | 7.827 | 8.875 | +13.414 |
| epsilon = alpha_ir = 1.00 | -15.750 | -15.228 | -10.690 |
| Q_internal = 0 W | -22.354 | -22.190 | -17.651 |
| Q_internal = 10 W | 10.544 | 11.770 | +16.309 |
| mass = 0.5x (2.5 kg) | -13.199 | -10.655 | -6.116 |
| mass = 2x (10 kg) | 3.322 | 3.390 | +7.929 |
| A_radiating = 0.04 m² | 14.972 | 16.261 | +20.799 |
| A_radiating = 0.08 m² | -20.475 | -20.055 | -15.516 |
| altitude = 400 km | -5.108 | -4.398 | +0.141 |
| altitude = 600 km | -5.413 | -4.698 | -0.160 |

### Interpretation

Over this five-orbit window, the strongest drivers are:

1. **Radiating area** — smaller area reduces emission strongly and warms the node.
2. **Internal power** — always-on heat; removing or doubling it moves final T by ~17 K.
3. **Emissivity** — higher `epsilon` cools more (even with matching higher Earth-IR absorptivity).
4. **Solar absorptivity** — affects direct sun and albedo together.
5. **Mass / capacitance** — changes how fast temperature responds in this transient; it is not a steady heat source/sink.
6. **Altitude (400–600 km)** — small effect here compared with optical and power assumptions.

### Assumptions and limitations

- One-at-a-time sweeps omit parameter interactions.
- Five orbits is still a transient; rankings could shift for a much longer run toward periodic steady state.
- Altitude changes period, eclipse fraction, and Earth view factor together.
- Plots shade baseline eclipse intervals; altitude cases have slightly different timing.
- No claim of accuracy for real SAR satellites.

## Phase 5 / final GUI

`app.py` is an interactive browser UI. It collects inputs and calls the
verified solvers. It does **not** re-implement the energy balance.

### Modes

1. **Single simulation** — one temperature history with eclipse shading.
2. **Baseline vs modified** — default reference case vs the user’s case.
3. **Environmental heating comparison** — solar-only, +Earth IR, +Earth IR + albedo.

### Synchronized views

One time slider drives:

- Plotly 3D Earth / orbit / sun direction / cylindrical shadow / satellite
- Temperature-plot cursor
- Live heat-flow breakdown (`Q_solar`, `Q_earth_ir`, `Q_albedo`, `Q_internal`,
  `Q_radiated`, `Q_net`)

Completed results stay in `st.session_state` until you click **Run simulation**
again, so editing widgets does not wipe the last solve.

### How to run

```text
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

If Streamlit occupies a terminal, open a second terminal for Git commands, or
press Ctrl+C to stop the app.

### Phase 3B time-step convergence

```text
python scripts/verify_phase3b_convergence.py
```

Five orbits with Earth IR + albedo:

| dt (s) | Tmin (°C) | Tfinal (°C) | ΔTfinal vs 0.5 s (K) |
| --- | --- | --- | --- |
| 10 | -5.2547 | -4.5448 | -7.8e-3 |
| 5 | -5.2476 | -4.5372 | -2.0e-4 |
| 1 | -5.2504 | -4.5386 | -1.6e-3 |
| 0.5 | -5.2488 | -4.5370 | 0 |

Final temperatures stay within about 0.01 K across these steps. Small
non-monotonic differences can appear because eclipse entry/exit is sampled at
the start of each Euler step.

### Physics consistency note

NASA smallsat thermal guidance uses the same load categories: solar, albedo,
planetshine (Earth IR), internal generation, storage, and radiation. This model
follows that structure for one node. A known modelling limitation remains:
emission is computed as `εσA T^4` to a 0 K sink while Earth IR is added
separately, rather than a full radiosity enclosure exchange.

See [`REFERENCES.md`](REFERENCES.md) for public sources and claim boundaries.

### Remaining limitations

- Single lumped node; no multi-node conduction network.
- Legacy mode uses fixed effective areas; enhanced mode adds rectangular-bus
  face solar absorption and face-sum emission with prescribed attitudes only
  (not closed-loop ACS).
- Earth IR and albedo remain Version 1.0 effective-area loads in both modes.
- 3D wing panels are visual-only and are not thermal surfaces.
- No experimental / flight validation.
- 3D scene is illustrative geometry synchronized to the orbit/eclipse
  state and prescribed bus orientation, not a photoreal mission animation.

## Version 2.0 — Checkpoint 2: attitude-dependent solar heating

### Model modes

| Mode | Solar absorption | Radiative emission | Earth IR / albedo |
| --- | --- | --- | --- |
| **Legacy** (default) | `α A_projected S` when sunlit | `ε σ A_radiating T⁴` | V1 effective areas |
| **Enhanced** | `Σ α_i S A_i max(0, n_i·s)` | `Σ ε_i σ A_i T⁴` | V1 effective areas (retained) |

Legacy mode with β = 0° preserves the Version 1.0 reference finals. Enhanced
mode with a 0.1 m cube, fixed-inertial attitude, and β = 0° reproduces the
same solar and radiation terms because only the +X face is sunlit and
`A_total = 0.06 m²`.

### Coordinate systems

- **Inertial:** Earth centre; orbit in XY; Sun `s = (cos β, 0, sin β)` toward
  the Sun (same convention as the cylindrical eclipse test).
- **Orbital basis:** `r̂`, `θ̂`, `ĥ` with `r̂ × θ̂ = ĥ`.
- **Body:** right-handed +X, +Y, +Z; length/width/height along those axes.

### Attitude modes (prescribed geometry only)

1. **Fixed inertial** — body axes = inertial XYZ.
2. **Nadir-pointing** — +Z = nadir (−`r̂`), +X = along-track (`θ̂`), +Y completes RH.
3. **Sun-pointing** — +X = `s`; +Y from `ĥ × s`, with fallback to `θ̂` (then
   inertial) when `|s · ĥ|` is too close to 1 (singular roll reference).

### Planetary heating choice (Checkpoint 2)

Attitude-dependent solar heating does **not** automatically make Earth IR or
albedo attitude-dependent. This checkpoint **retains** the Version 1.0
effective-area planetary loads and labels that limitation explicitly.
Implementing face-to-Earth view factors is deferred.

### Sources

Face solar heating `Q = α S A max(0, n·s)` follows the standard projected-area
/ incidence-angle form used in small-satellite thermal notes (e.g. NASA
SmallSat Institute materials and Cottingham / TFAWS on-orbit environment
lectures). See [`SOURCE_TRACEABILITY.md`](SOURCE_TRACEABILITY.md).

## Version 2.0 — Checkpoint 3: time-dependent internal power

### Energy balance

```text
m * cp * dT/dt = Q_solar(t) + Q_earth_ir(t) + Q_albedo(t) + Q_internal(t) - Q_radiated(t)
```

`Q_internal(t)` is evaluated at the **start** of each explicit Euler step, using
the same time and eclipse flag as solar gating.

### Schedule kinds

| Kind | Rule |
| --- | --- |
| `constant` | `Q_internal =` GUI Internal heat (W); default 5 W (V1) |
| `eclipse_reduced` | sunlight → nominal W; eclipse → standby W (actual β-aware eclipse) |
| `periodic_high` | within each period `[nP,(n+1)P)`, high on `[nP, nP+D)`, else base |
| `custom_intervals` | half-open `[start,end)`; no overlaps; else baseline Internal heat |

### Numerical note (Euler discontinuities)

Explicit Euler still holds all loads constant over a completed step, and the
user-selected `time_step_s` remains the **maximum** step.

For `periodic_high` and `custom_intervals`, the integrator queries
`next_scheduled_transition_s` and **shortens** a step that would cross a known
power discontinuity so the next sample begins exactly on the half-open
boundary. That prevents short off-grid pulses (for example a 1 s pulse inside a
5 s nominal step) from being skipped. Remaining time after the event continues
with the updated `Q_internal` under the same maximum-step limit.

**Pulse energy terminology.** A scheduled pulse that sets total internal power to
100 W for one second while the baseline schedule is 5 W contributes
`(100 − 5) × 1 s = 95 J` of *additional* energy relative to the baseline (not
100 J). The absolute energy delivered by the pulse interval itself is
`100 W × 1 s = 100 J`. Independent off-grid checks in this repository report the
additional 95 J figure so temperature deltas can be compared against
`ΔE / (m · cp)`.

`constant` schedules take the ordinary fixed-step path (Version 1.0 baselines
unchanged).

`eclipse_reduced` still uses the **sampled** cylindrical-eclipse flag at each
step start. Eclipse entry/exit are **not** treated as separate schedule events
in Checkpoint 3; resolving them remains an orbital time-step approximation
(same class of limitation as the legacy solar eclipse gate).

### GUI sample inspection and resource limits

Event-aware stepping produces **nonuniform** timestamps. The Streamlit time
control therefore selects a **stored sample index** (with physical time
readouts) so every power-transition sample remains reachable. Instantaneous
heat-flow, power-state, temperature marker, and 3D views stay synchronized to
that index on the inspected curve.

Interactive runs estimate samples as nominal Euler count **plus** scheduled
power-event splits, and reject requests above `MAX_GUI_SAMPLES` (250 000). The
solver also enforces `max_samples` at runtime and raises rather than returning a
truncated history that could be mistaken for a complete orbit set.

### Illustrative power levels

Default standby / nominal / high-power values (1 / 5 / 15 W) are **illustrative
assumptions (C)**, not a published spacecraft power budget. No battery or EPS
model is included.

## Version 2.0 — Checkpoint 4: hot / nominal / cold screening scenarios

### Modelling convention choice

Two common LEO environmental screening conventions were considered:

| Convention | Idea | Used here? |
| --- | --- | --- |
| NASA Preferred Practice GD-AP-2301 energy-balance triples | Seasonal solar + paired albedo; `E_olr = (1−a)S/4` | **Yes** for Hot/Cold fluxes |
| ERBE / STEM / mission NEDD statistical albedo–OLR pairs | Inclination- and time-constant-dependent extremes where max albedo and max OLR are not stacked independently | Documented alternative only |

Because this simulator holds planetary albedo and OLR **constant** over an orbit
(Version 1.0 effective-area Earth loads), energy-balance triples are the
physically consistent match. Statistical ERBE pairs remain valuable for
mission design with short thermal time constants but are **not** the preset
basis here.

GD-AP-2301 Table 1 combinations are intended for **orbit-average** screening
analyses. In this GUI they are applied as **simplified constant** environmental
parameters (fixed S, a, and E_olr for every time step), matching the repository’s
constant-load Earth IR / albedo model rather than computing orbit-averaged
incident heat rates on oriented surfaces.

Independently stacking every maximum (or every minimum) environmental and
operational input was rejected as non-defensible for screening.

### Preset table (500 km educational spacecraft)

| Parameter | Nominal | Hot screening | Cold screening | Classification |
| --- | --- | --- | --- | --- |
| Solar irradiance `S` | 1361 W/m² | 1422 W/m² | 1318 W/m² | Nominal: repo V1 (C); Hot/Cold: NASA GD-AP-2301 winter/summer (B) |
| Earth Bond albedo `a` | 0.30 | 0.35 | 0.25 | Nominal: repo/GD-AP-2301 nominal (B/C); Hot/Cold: GD-AP-2301 (B) |
| Earth OLR `E_olr` | 240 W/m² | `(1−0.35)×1422/4 ≈ 231.075` W/m² | `(1−0.25)×1318/4 ≈ 247.125` W/m² | Nominal: repo V1 (C); Hot/Cold: derived from GD-AP-2301 formula (D from B) |
| Orbital beta `β` | 0° | just above `β_c(h)` (≈ 70° at 500 km) | 0° | Nominal: V1 reference (C); Hot/Cold beta choice: illustrative screening (C) |
| Earth IR + albedo flags | both on | both on | both on | Modelling assumption (C) |
| Internal power | constant 5 W | constant 15 W | constant 1 W | Illustrative operating levels (C); ECSS training notes high/low dissipation for hot/cold cases as a practice, not a wattage mandate |
| Geometry / α / ε | unchanged | unchanged | unchanged | User-controlled; EOL coating degradation is **not** applied |

**Important:** Hot OLR is *lower* than Cold OLR under energy balance. The Cold
case is still colder because of lower solar, lower albedo, maximum eclipse
(`β = 0°`), and lower internal power.

Presets are **screening scenarios**, not universal worst-case spacecraft
conditions. Custom mode leaves sidebar values unchanged.

### GUI behaviour

- Scenario selector: Nominal / Hot / Cold / Custom.
- While Nominal / Hot / Cold is selected, preset-owned inputs (S, a, E_olr, β,
  constant internal power, power-schedule kind, and planetary-load flags) are
  **locked** and re-synchronized from the preset definition (Hot β updates when
  altitude changes). Custom re-enables editing with no hidden overrides.
- Compare Hot/Nominal/Cold mode solves all three overlays on shared spacecraft
  settings (mass, coatings, areas, altitude, step, thermal model, attitude).
- Existing single, reference-compare, and A/B/C environment modes remain and
  may optionally apply one preset overlay before solving.

## Version 2.0 — Checkpoint 5: CubeSat-inspired configurations

### CDS mechanical envelopes (sourced)

Cal Poly **CubeSat Design Specification (CDS) Rev 14.1** (February 2022) defines
form-factor envelopes and typical maximum masses (Table 1 / Appendix B):

| Form factor | Envelope (mm) | Typical max mass (kg) |
| --- | --- | --- |
| 1U | 100.0 × 100.0 × 113.5 | 2.00 |
| 3U | 100.0 × 100.0 × 340.5 | 6.00 |

PDF: https://www.nasa.gov/wp-content/uploads/2018/01/cubesatdesignspecificationrev14_12022-02-09.pdf

The 100 mm cross-section is the rail envelope; Z includes rail/standoff extent
beyond a naïve 100 mm “unit cube.” Extra “tuna can” volume for some 3U
dispensers is **not** modelled here.

**Idealized radiating geometry.** The rectangular L×W×H bus used for face solar
absorption and face-sum radiation is an **idealized closed envelope**, not an
exact representation of exposed flight-hardware surfaces (rails, gaps,
connectors, antennas, multi-layer insulation layups, or deployables). Exterior
area in this model equals the six faces of that rectangular prism.

### Configurations in this repository

| Preset | Dimensions | Mass used here | Thermal model | Classification |
| --- | --- | --- | --- | --- |
| Legacy simplified | 0.1 m cube (viz) | 5 kg | Legacy fixed areas 0.01 / 0.06 m² | Repo V1 educational (C) |
| Illustrative 0.1 m cube | 0.1 × 0.1 × 0.1 m | 5 kg | Enhanced; A_rad = 0.06 m² | Illustrative (C) |
| Generic 1U-inspired | CDS 1U envelope | 1.50 kg (under 2.00 kg max) | Enhanced; areas from faces | Envelope (B); mass/cp/α/ε (C) |
| Generic 3U-inspired | CDS 3U envelope | 4.00 kg (under 6.00 kg max) | Enhanced; areas from faces | Envelope (B); mass/cp/α/ε (C) |
| Custom | User | User | User | User |

Effective `cp = 900 J/(kg·K)` is a **lumped** whole-spacecraft approximation
(structure + electronics + batteries, etc.), **not** derived from aluminium
rail material alone and **not** specified by the CDS.

### Derived exterior areas

For length `l`, width `w`, height `h` along body +X/+Y/+Z:

```text
A_±x = w h
A_±y = l h
A_±z = l w
A_total = 2 (w h + l h + l w)
```

Enhanced solar heating sums face contributions `α_i S A_i max(0, n_i·s)`.
Enhanced radiation sums `ε_i σ A_i T⁴` over the same six faces (no
double-counting). Visual solar wings remain decorative only.

### GUI behaviour

Spacecraft presets lock and synchronize dimensions, mass, effective cp, optics,
thermal-model kind, and related area fields so the sidebar cannot contradict
the solver. Custom unlocks editing. Hot/Nominal/Cold scenario compare continues
to share one spacecraft configuration across all three environmental cases.
