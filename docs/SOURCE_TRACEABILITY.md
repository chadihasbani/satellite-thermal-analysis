# Source traceability register

This register classifies important modelling inputs and relations used by the
simulator. It supports scientific transparency; it does **not** claim
NASA/ESA endorsement or experimental validation of the software.

## Classification key

| Tag | Meaning |
| --- | --- |
| **A** | Established physical principle |
| **B** | Externally sourced engineering data or published method |
| **C** | Illustrative modelling assumption for this educational simulator |
| **D** | Derived or calculated result from selected inputs and equations |

## Constants and environment

| Item | Value / Equation | Units | Classification | Source | Specific reference | Implementation notes |
| --- | --- | --- | --- | --- | --- | --- |
| Stefan–Boltzmann constant `σ` | `5.670374419e-8` | W/(m²·K⁴) | B | CODATA / NIST family of constants | Common CODATA 2018 value for σ | Used in `Q_radiated = ε σ A T⁴` |
| Solar irradiance `S` (default) | 1361 | W/m² | C (with B context) | Modern TSI / solar-constant scale | Order-of-magnitude modern total solar irradiance near 1361 W/m²; exact citation to be tightened in later stages | Default input; not a mission-specific design case |
| Earth Bond albedo `a` | 0.30 | — | C | Common global-mean engineering note | See `docs/REFERENCES.md` | Illustrative global-mean class value |
| Earth OLR `E_olr` | 240 | W/m² | C | Common TOA OLR magnitude | See `docs/REFERENCES.md` | Illustrative; real OLR varies |
| Earth radius `R_E` | 6 371 000 | m | C/B | Spherical-Earth modelling choice | Mean-radius class value used throughout V1 | Spherical planet; not WGS84 ellipsoid dynamics |
| Earth `μ` | `3.986004418e14` | m³/s² | B | Standard GM Earth value used in orbital mechanics | Conventional value matching prior V1 baselines | Circular Keplerian period only |

## Orbital geometry, beta, and eclipse

| Item | Value / Equation | Units | Classification | Source | Specific reference | Implementation notes |
| --- | --- | --- | --- | --- | --- | --- |
| Circular period | `T = 2π √(r³/μ)` | s | A | Newtonian / Keplerian circular orbit | Standard orbital mechanics | `r = R_E + h` |
| Beta definition | Angle between Sun vector and orbital plane | rad | A/B | Thermal-engineering orbital geometry | Rickman, S., *Introduction to On-Orbit Thermal Environments*, TFAWS 2023, https://tfaws.nasa.gov/wp-content/uploads/16.On-Orbit-Thermal-Environments-TFAWS-2023_SRickman.pdf (beta definition and eclipse discussion; accessed for Checkpoint 1) | Implemented as `s = (cos β, 0, sin β)` with orbit in XY |
| Cylindrical umbra test | `r·s < 0` and `|r × s| ≤ R_E` | — | B/C | Ideal cylindrical shadow for distant Sun | Same TFAWS notes: cylindrical-shadow simplification when penumbra is neglected | No atmosphere, refraction, or penumbra |
| Critical beta | `β_c = asin(R_E / r)` | rad | D | Project derivation from cylinder geometry | Independently derived; TFAWS notes that eclipse vanishes above a high `|β|` for a given altitude (example ~71° at 408 km). At 500 km with `R_E = 6371 km`, `β_c ≈ 68.007°` | **Not** `acos(R_E/r)`. Tangency: `|sin β| = R_E/r` at anti-sun |
| Analytical eclipse duration | `t = (T/π) asin(κ)`, `κ = √(((R/r)² − sin²β)/cos²β)` for `|β| < β_c`; else 0 | s | D | Project derivation from the same cylinder test | Same geometry as the discrete `in_cylindrical_earth_shadow` test | At `|β| = β_c` analytical duration = 0 (measure-zero contact) |
| Numerical eclipse duration | Sum of time steps with shadow test true | s | D | Implementation sampling | Agrees with analytical within ~2 `dt` | V1 β = 0 reference preserved |

## Solar heating and spacecraft

| Item | Value / Equation | Units | Classification | Source | Specific reference | Implementation notes |
| --- | --- | --- | --- | --- | --- | --- |
| Legacy direct solar | `Q_solar = α A_projected S` (sunlit); 0 in eclipse | W | A/C | Energy balance; fixed projected area | NASA SmallSat SOA thermal energy-balance categories | Default / Version 1.0 path |
| Enhanced face solar | `Q_i = α_i S A_i max(0, n_i·s)`; `Q_solar = Σ Q_i` | W | A/B | Projected-area / incidence form for spacecraft surfaces | Cottingham, C., *Spacecraft Thermal Control* lecture notes (ENAE 691), NTRS 20230001953 (accessed Checkpoint 2): absorbed solar uses `A cosθ` / optical properties; SmallSat LEO thermal notes use `α S A cosθ` for sunward faces | `s` is the unit vector toward the Sun (same as eclipse). Eclipse sets `S = 0` |
| Enhanced radiation | `Q_rad = Σ ε_i σ A_i T⁴` | W | A | Stefan–Boltzmann emission from each exterior face | Standard radiation; isothermal single-node assumption | Face-summed over the six bus faces only. **Deep-space / 0 K sink:** emission uses `εσA T⁴` with no incoming IR from space; Earth IR is a separate load (V1 effective-area term), not a coupled radiosity exchange |
| Default bus size | 0.1 × 0.1 × 0.1 m cube | m | C | Illustrative | Chosen so face area 0.01 m² and `A_total` 0.06 m² match V1 defaults | Not a published vehicle; CubeSat presets are Checkpoint 5 |
| Absorptivity / emissivity | 0.60 / 0.80 | — | C | Illustrative coating-like pair | Not a published spacecraft finish for a named vehicle | Uniform on all faces unless face_optics supplied |
| Attitude modes | fixed inertial / nadir / sun-pointing | — | C/D | Prescribed geometric orientations | LVLH-like nadir convention; sun-pointing with documented singular roll fallback | Not closed-loop ACS |
| Earth IR / albedo (enhanced) | V1 effective-area formulas retained | W | C | Explicit Checkpoint 2 modelling choice | — | **Not** face-to-Earth view factors; labelled limitation |
| Areas / mass / `c_p` | See defaults | — | C | Educational single-node inputs | V1 defaults retained | Not a CubeSat CDS claim yet |

## Internal power and scenarios

| Item | Value / Equation | Units | Classification | Source | Specific reference | Implementation notes |
| --- | --- | --- | --- | --- | --- | --- |
| Internal power | 5 W constant | W | C | Illustrative dissipation | — | Time-dependent schedules deferred to Checkpoint 3 |
| Hot/cold scenarios | — | — | — | — | — | Checkpoint 4 |

## Verification notes

### Checkpoint 1

- Independent tests in `tests/test_beta_angle.py` rebuild `β_c` and `t_eclipse` without trusting a single helper as the only definition.
- Antisun cylinder membership flips across `|sin β| = R_E/r`.
- β = 0° recovers the V1 closed-form `T asin(R/r)/π`.
- 3D umbra mesh axis follows `-s` for nonzero beta.

### Checkpoint 2

- Independent illumination cases: sun-facing, perpendicular, back-facing, multi-face (`tests/test_attitude_solar.py`).
- Enhanced fixed-inertial 0.1 m cube at β = 0° matches legacy temperature history.
- GUI modes propagate `thermal_model` / `attitude_mode` / body dimensions (Reference case in spacecraft-settings compare stays on defaults).
- 3D bus axes use the same `body_axes_inertial` helper as the solar calculation; wings labelled visual-only.

## Known limitations

- Using a published beta/eclipse or solar-heating discussion does not validate this code as flight software.
- Planetary IR/albedo geometry is still the V1 effective-area model.
- Penumbra and finite Sun angular size are omitted.
- Prescribed attitudes are not ACS dynamics; solar panels in the 3D view are not thermal faces.
