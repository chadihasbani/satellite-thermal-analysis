# Satellite thermal analysis — Phase 1

A simplified **single-node, transient** thermal model of a small satellite in
continuous sunlight. This is a learning project for AI-assisted engineering
software. It does **not** predict the temperature of a real satellite.

Phase 1 stops at the lumped energy balance, explicit Euler integration, a
temperature plot, and unit tests. Orbital geometry, eclipse, Earth infrared,
albedo, and a GUI are intentionally absent.

## Equation

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
main.py                         Run the 90-minute study and save the plot
verify_phase1.py                Print equilibrium and time-step checks
satellite_thermal/
    parameters.py               Named inputs, units, and validation
    validation.py               Shared numeric checks
    heat_transfer.py            Q_solar, Q_radiated, and dT/dt
    simulation.py               Explicit Euler in continuous sunlight
    equilibrium.py              Analytical steady temperature
    verification.py             Long-run and time-step comparisons
    units.py                    Kelvin to Celsius for display
    plotting.py                 Temperature-time figure
tests/test_heat_transfer.py     Heat-rate and input checks
tests/test_verification.py      Equilibrium and convergence checks
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
