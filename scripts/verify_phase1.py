"""Print Phase 1 equilibrium and time-step verification.

The physical parameters and the 90-minute Phase 1 plot are left unchanged.
"""

import _bootstrap  # noqa: F401

from satellite_thermal.verification import verification_report


def main() -> None:
    print(verification_report())


if __name__ == "__main__":
    main()
