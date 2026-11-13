"""Print the Phase 3B orbital time-step convergence study."""

import _bootstrap  # noqa: F401

from satellite_thermal.phase3b_convergence import (
    format_convergence_report,
    run_phase3b_timestep_convergence,
)


def main() -> None:
    rows = run_phase3b_timestep_convergence()
    print(format_convergence_report(rows))


if __name__ == "__main__":
    main()
