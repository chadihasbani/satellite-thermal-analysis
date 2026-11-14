# Engineering references

The references below provide spacecraft-engineering context for the energy
balance, optical properties, albedo, planetary infrared, and eclipse geometry.
They do **not** endorse this code. This repository is not flight software.

## Distinction of claims

| Category | Meaning in this project |
| --- | --- |
| Sourced physical principles | Energy balance among solar, albedo, planetshine, dissipation, storage, radiation |
| Published engineering methods | Smallsat thermal literature uses those loads and optical properties |
| Illustrative input assumptions | Defaults such as `a = 0.30`, `E_olr = 240 W/m²`, `α = 0.60`, `ε = 0.80` |
| Model-specific simplifications | Single node, fixed areas, cylindrical shadow, emission to a 0 K sink |
| Numerical verification | Unit tests, equilibrium checks, eclipse geometry, timestep studies |
| Experimental validation | **Not performed** |

## Accessed sources

### 1. NASA Small Spacecraft Technology — Thermal Control

- https://www.nasa.gov/smallsat-institute/sst-soa/thermal-control/
- PDF chapter: https://www.nasa.gov/wp-content/uploads/2025/02/7-soa-thermal-2024.pdf

NASA states the spacecraft thermal energy balance in the form:

`q_solar + q_albedo + q_planetshine + Q_gen = Q_stored + Q_out,rad`

It also emphasizes the two-waveband optical model: solar absorptivity for
solar/albedo loads and infrared emissivity for IR exchange and emission.

**Relation to this project:** the governing ODE uses the same load categories
for one lumped node. Solar absorptivity applies to direct sun and albedo;
infrared emissivity / absorptivity apply to emission and Earth IR.

### 2. NASA Small Spacecraft Technology State-of-the-Art report

- https://www.nasa.gov/smallsat-institute/sst-soa/

Used for small-spacecraft thermal-control context and terminology.

### 3. NASA — Introduction to Orbital Mechanics and Spacecraft Attitudes for Thermal Engineers

- NTRS PDF: https://ntrs.nasa.gov/api/citations/20205003902/downloads/Introduction%20to%20Orbital%20Mechanics%20and%20Spacecraft%20Attitudes%20for%20Thermal%20Engineers%20CHARTS%20PDF.pdf

Used for orbital / eclipse thinking relevant to thermal engineers (beta angle,
sunlight/eclipse, attitude effects). This code uses a simplified circular orbit
and cylindrical shadow with selectable beta (default 0 for the V1 reference).

### 3b. Cottingham — Spacecraft Thermal Control lecture (ENAE 691)

- NTRS PDF: https://ntrs.nasa.gov/api/citations/20230001953/downloads/ENAE%20691%20Spring23%20Thermal%20Cottingham.pdf
- Accessed for Checkpoint 2.

States that environmental heat transfer to a satellite surface depends on
orientation and optical properties, with projected area `A_p = A cos θ` for
solar loading. Used as supporting context for the enhanced-mode face relation
`Q_i = α_i S A_i max(0, n_i · s)`. This project’s implementation and singular
attitude handling are documented in `docs/MODEL.md`.

### 3c. Rickman — Introduction to On-Orbit Thermal Environments (TFAWS 2023)

- https://tfaws.nasa.gov/wp-content/uploads/16.On-Orbit-Thermal-Environments-TFAWS-2023_SRickman.pdf
- Accessed for Checkpoint 1 documentation.

Defines beta as the angle between the solar vector and the orbital plane,
discusses eclipse/umbra including a cylindrical-shadow simplification, and
shows that eclipse fraction falls with rising `|β|` and vanishes above a
critical high-beta regime for a given altitude. The project's
`β_c = asin(R_E/r)` and closed-form eclipse duration are independently
derived from the cylinder test implemented in code (see
`docs/SOURCE_TRACEABILITY.md` and `docs/MODEL.md`).

### 4. Thermal analysis and control of small satellites in low Earth orbit

- https://s3vi.ndc.nasa.gov/ssri-kb/static/resources/Thermal%20analysis%20and%20control%20of%20small%20satellites%20in%20low%20Earth%20orb.pdf

Discusses LEO environmental loads (solar, Earth IR, albedo), lumped thermal
modelling, and numerical energy-balance approaches for small satellites.

## Supporting public engineering notes

- Preferred-practice / on-orbit environment notes commonly cite nominal Earth
  Bond albedo near 0.30 and Earth-emitted IR near ~240–241 W/m². Those are
  order-of-magnitude context values, not mission-specific design inputs.

## Illustrative inputs used here

| Input | Value | Notes |
| --- | --- | --- |
| Solar constant `S` | 1361 W/m² | Common modern solar-irradiance scale |
| Earth Bond albedo `a` | 0.30 | Nominal global-mean albedo class value |
| Earth OLR `E_olr` | 240 W/m² | Illustrative TOA outgoing longwave magnitude |
| `alpha`, `epsilon` | 0.60, 0.80 | Assumed coating-like optical properties |
| Internal power (constant) | 5 W | Version 1.0 educational default |
| Standby / nominal / high | 1 / 5 / 15 W | Checkpoint 3 illustrative operating levels only |

These defaults are documented modelling choices for this repository. They are
**not** “official NASA design inputs” for a specific spacecraft. Scheduled
internal-power profiles do **not** represent a real electrical power subsystem.

## Unavailable / unused

An ESA Thermal Workshop proceedings PDF previously considered
(`exchange.esa.int/.../ESA-WPP-207-complete.pdf`) was not accessible at the
time of documentation. No ESA-specific quotations are taken from that file.
