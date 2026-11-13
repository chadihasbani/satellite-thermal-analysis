# Satellite thermal analysis

A simplified **single-node, transient** thermal model of a small satellite.
This is a learning project for AI-assisted engineering software. It does
**not** predict the temperature of a real satellite.

Phase 1 is the lumped energy balance in continuous sunlight. Phase 2 keeps
that balance and adds a circular low-Earth orbit. Direct solar heating is
turned off only while a cylindrical Earth-shadow test says the satellite is
in eclipse. Earth infrared, albedo, and a GUI are still absent.

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
satellite_thermal/
    parameters.py               Named thermal inputs, units, and validation
    validation.py               Shared numeric checks
    heat_transfer.py            Q_solar, Q_radiated, and dT/dt
    simulation.py               Explicit Euler in continuous sunlight
    equilibrium.py              Analytical steady temperature
    verification.py             Long-run and time-step comparisons
    orbit.py                    Period, position, and cylindrical shadow
    orbital_simulation.py       Sunlight/eclipse march of the same energy balance
    orbital_plot.py             Temperature plot with shaded eclipse intervals
    units.py                    Kelvin to Celsius for display
    plotting.py                 Phase 1 temperature-time figure
tests/test_heat_transfer.py     Heat-rate and input checks
tests/test_verification.py      Equilibrium and convergence checks
tests/test_orbit.py             Period, shadow geometry, and eclipse heating
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
- No Earth infrared or albedo. Those loads would warm the node in eclipse and
  are reserved for a later phase.
- The Phase 1 continuous-sunlight case remains `python main.py`.
