# Development notes

This document records how the project was developed and organized. It is
technical process documentation for maintainers and reviewers, not a product
manual. For equations and assumptions, see [`MODEL.md`](MODEL.md). For how to
run the tool, see the root [`README.md`](../README.md).

## Development approach

The model was built in phases, keeping previously verified solvers intact while
new capability was added:

1. Lumped thermal energy balance and explicit Euler integration
2. Circular LEO orbit and cylindrical eclipse geometry
3. Earth infrared heating, then Earth albedo
4. Parameter sensitivity studies
5. Streamlit GUI with synchronized 3D orbit view and heat-flow diagnostics
6. Version 2 physics checkpoints (beta, face-based heating, CubeSat
   configurations) with integration verification
7. PDF engineering reports and public-release documentation
8. Product simplification: two analysis modes, constant power, fixed-inertial
   orientation only, and a cleaner Streamlit UI

Physics live in `satellite_thermal/`. The GUI (`app.py`) and CLI scripts under
`scripts/` call those solvers; they do not re-implement the thermal equations.
PDF reporting (`satellite_thermal/report_pdf.py`) formats completed study
results only — it does not re-solve the thermal model.

## AI-assisted development

Parts of this repository were developed with **Cursor** coding agents.

AI assistance was used to:

- accelerate implementation of well-specified modules and tests
- iterate on GUI layout and documentation wording
- propose refactors that kept the physics package separated from presentation

Human review remained responsible for:

- governing equations and modelling assumptions
- numerical verification strategy
- accepting or rejecting agent changes
- final documentation accuracy

This is ordinary modern engineering practice: agents speed iteration; tests and
review keep the result honest. The automated test suite and documented
assumptions are the primary evidence that the model behaves as specified.

## Repository conventions

| Area | Convention |
| --- | --- |
| Physics / numerics | `satellite_thermal/` |
| Interactive UI | `app.py` |
| CLI studies | `scripts/` |
| Tests | `tests/` (`python -m unittest discover -s tests -v`) |
| Detailed model notes | `docs/MODEL.md` |
| References | `docs/REFERENCES.md` |
| Verification summary | `docs/VERIFICATION.md` |
| PDF report notes | `docs/PDF_REPORT.md` |
| Generated CLI / PDF samples | `outputs/` (mostly gitignored) |
| Doc screenshots / example figures | `docs/images/` |

## Related documents

- [`../README.md`](../README.md) — overview, install, run
- [`MODEL.md`](MODEL.md) — equations, assumptions, verification notes
- [`VERIFICATION.md`](VERIFICATION.md) — integrated verification summary
- [`PDF_REPORT.md`](PDF_REPORT.md) — engineering PDF report
- [`REFERENCES.md`](REFERENCES.md) — engineering references and claim boundaries
