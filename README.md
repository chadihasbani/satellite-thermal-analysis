# Satellite thermal analysis

A simplified **single-node, transient** thermal model of a small satellite.
This is a learning project for AI-assisted engineering software. It does
**not** predict the temperature of a real satellite.

Phase 1 is the lumped energy balance in continuous sunlight. Phase 2 keeps
that balance and adds a circular low-Earth orbit. Direct solar heating is
turned off only while a cylindrical Earth-shadow test says the satellite is
in eclipse. Phase 3A optionally adds simplified Earth infrared heating.
Phase 3B optionally adds angle-dependent Earth albedo. Phase 4 studies
parameter sensitivity around the Phase 3B baseline. Phase 5 adds a Streamlit
GUI that calls the same verified solvers.

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
- Explicit Euler is a first-order teaching method. A 1-second step is small
  relative to this node's thermal response, but the result is still a numerical
  approximation of this simplified equation.

## Layout

```text
main.py                         Phase 1: 90 minutes of sunlight and its plot
verify_phase1.py                Phase 1 equilibrium and time-step checks
run_phase2.py                   Phase 2: five orbits and the eclipse plot
run_phase3a.py                  Phase 3A: Phase 2 vs Earth-IR comparison
run_phase3b.py                  Phase 3B: Earth IR vs Earth IR + albedo
run_phase4.py                   Phase 4: parameter sensitivity study
app.py                          Phase 5: Streamlit GUI
satellite_thermal/
    parameters.py               Named thermal inputs, units, and validation
    validation.py               Shared numeric checks
    heat_transfer.py            Heat rates and optional planetary loads
    simulation.py               Explicit Euler in continuous sunlight
    equilibrium.py              Analytical steady temperature
    verification.py             Long-run and time-step comparisons
    orbit.py                    Period, position, and cylindrical shadow
    orbital_simulation.py       Sunlight/eclipse march; optional IR/albedo
    orbital_plot.py             Phase 2 temperature plot with eclipses
    earth_infrared.py           View factor and absorbed Earth IR
    albedo.py                   Angle-dependent Earth albedo heating
    comparison_plot.py          Phase comparison figures
    sensitivity.py              One-at-a-time sensitivity cases
    sensitivity_plot.py         Sensitivity group temperature plots
    gui_support.py              GUI input assembly and figure helper
    units.py                    Kelvin to Celsius for display
    plotting.py                 Phase 1 temperature-time figure
tests/test_heat_transfer.py     Heat-rate and input checks
tests/test_verification.py      Equilibrium and convergence checks
tests/test_orbit.py             Period, shadow geometry, and eclipse heating
tests/test_earth_infrared.py    Earth IR heating and compatibility checks
tests/test_albedo.py            Albedo heating and compatibility checks
tests/test_sensitivity.py       Sensitivity study checks
tests/test_gui_support.py       GUI wiring checks
requirements.txt
```

## Run

```text
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python main.py
```

`python main.py` writes `outputs/phase1_temperature.png`. Add `--show` to open
a window. Change the step with `--time-step 0.5` (seconds).

```text
python run_phase2.py
```

writes `outputs/phase2_temperature.png` for five orbits at a 1 s step.
`--orbits` and `--time-step` change that run. Phase 1 is still `python main.py`.

```text
python run_phase3a.py
```

writes `outputs/phase3a_earth_ir_comparison.png`, comparing five orbits without
and with Earth infrared heating.

```text
python run_phase3b.py
```

writes `outputs/phase3b_albedo_comparison.png`, comparing Earth IR only against
Earth IR plus albedo.

```text
python run_phase4.py
```

prints the sensitivity table and writes
`outputs/phase4_absorptivity.png`, `outputs/phase4_emissivity.png`, and
`outputs/phase4_internal_power.png`.

```text
python -m streamlit run app.py
```

opens the Phase 5 GUI in a browser. Defaults match the Phase 3B teaching
baseline. The default time step is 5 s for interactive use; set 1 s to match
the CLI studies.

```text
python verify_phase1.py
```

prints the equilibrium comparison and the time-step table below.

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
- The existing 90-minute plot and `python main.py` behavior are unchanged.

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

Phase 2 uses `beta = 0`, so the Sun is `+X` and lies in the orbital plane.
Position angle `theta` is measured from the sunward axis. The run starts at
`theta = 0`, which is the sun-facing side, above the subsolar point:

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

Eclipse is not a stored number of minutes. A position is in shadow when it is
on the night side of the terminator plane and inside a cylinder of radius
`R_earth` extending anti-sunward:

```text
r_vec · s_hat < 0
|r_vec × s_hat| <= R_earth
```

For this beta = 0 circle, that condition is true for an angle
`2 * asin(R_earth / r)` centered on the anti-sun point. The corresponding
duration is

```text
t_eclipse = T_orbit * asin(R_earth / r) / pi = 2141.523 s (35.692 min)
```

The thermal run samples that same test. With a 1 s step, a step is eclipse
when the test is true at the start of the step. That sampling gives

| Quantity | Value |
| --- | --- |
| Orbital period | 5668.1444 s (94.4691 min) |
| Eclipse per orbit | 2141.0000 s (35.6833 min) |
| Sunlight per orbit | 3527.1444 s (58.7857 min) |

The 0.523 s difference from the closed-form eclipse is the 1 s sampling of
the entry and exit. Eclipse plus sunlight equals one period. About 36 minutes
of eclipse in a 94.5-minute low-Earth orbit is the expected result for a
cylindrical shadow at beta = 0.

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
This is a teaching transient, not a flight prediction.

### Assumptions and limitations

- The orbit is circular. Altitude, beta, and the solar direction do not change.
- Earth is a smooth sphere. There is no atmosphere, refraction, or penumbra,
  so the shadow edge is sharp.
- Beta = 0 gives the longest eclipse for this altitude. A nonzero beta would
  shorten it, and a high enough beta would remove it. Phase 2 does not sweep
  beta.
- Projected area does not change with attitude. The satellite is still one
  isothermal node.
- Eclipse duration reported by the 1 s run is the sampled shadow test, so it
  can differ from `asin(R/r)` by less than one step.
- Phase 2 itself still leaves Earth infrared off. Phase 3A adds that load
  optionally. Albedo remains reserved for a later phase.
- The Phase 1 continuous-sunlight case remains `python main.py`.

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

`E_olr` is a teaching global-mean flux near the top of the atmosphere. It is
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
Adding `Q_earth_ir` separately is a common teaching decomposition. It is
physically useful for comparing load magnitude, but it is not an exact
spacecraft thermal model.

### Availability in sunlight and eclipse

`Q_earth_ir` is constant on the circular 500 km orbit and is applied in both
sunlight and eclipse. Direct solar heating is still zero only in eclipse.
`include_earth_infrared=False` remains the default in
`simulate_orbital_eclipse`, so `python run_phase2.py` and the Phase 2 tests
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

- Bond albedo `a = 0.30` is a common global-mean teaching value, not a local
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

This is a sensitivity study of the teaching model. It is **not** experimental
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

## Phase 5 — Streamlit GUI

Phase 5 adds an interactive browser UI in `app.py`. The GUI collects inputs and
calls `simulate_orbital_eclipse` through `satellite_thermal/gui_support.py`.
It does **not** re-implement the energy balance.

### Features

- Adjust mass, `cp`, optical properties, areas, internal power, and initial T
- Set altitude, orbit count, and time step
- Toggle Earth IR and albedo
- Run one case and view min / max / final temperatures
- Temperature-time plot with eclipse shading
- Kirchhoff pairing: `alpha_ir` is set equal to `epsilon`

### How to run

```text
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Defaults match the Phase 3B teaching baseline. The GUI default time step is
5 s for faster interaction. Use 1 s if you want closer agreement with the CLI
five-orbit studies.

### Limitations

- Single-run only. Phase 4 sensitivity sweeps remain in `run_phase4.py`.
- Local Streamlit app; nothing is published online.
- Still a teaching model, not flight software.
