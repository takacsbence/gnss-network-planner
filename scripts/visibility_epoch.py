import logging

from pathlib import Path
from datetime import datetime, timezone

from gnss_network_planner.navigation.loader import (
    load_ephemerides,
)

from gnss_network_planner.gnss.orbit_calculator import (
    OrbitCalculator,
)

from gnss_network_planner.utils.logging_utils import (
    setup_logging
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

NAV_FILE = (
    PROJECT_ROOT
    / "data"
    / "nav"
    / "BRDC00IGS_R_20252630000_01D_MN.rnx"
)

EPOCH = datetime(
    2025,
    9,
    20,
    12,
    0,
    0,
    tzinfo=timezone.utc,
)

SAT_SYSTEM = "C"
SAT_PRN = 25

setup_logging()
logger.info("GNSS Network Planner started")

def main():

    print("Loading navigation file...")

    db = load_ephemerides(
        NAV_FILE
    )

    print(
        f"Loaded {len(db)} ephemerides"
    )

    eph = db.get_closest(
        SAT_SYSTEM,
        SAT_PRN,
        EPOCH,
    )

    if eph is None:
        print(
            f"No ephemeris found for "
            f"{SAT_SYSTEM}{SAT_PRN:02d}"
        )
        return

    print(
        f"Selected ephemeris: "
        f"{SAT_SYSTEM}{SAT_PRN:02d}"
    )

    calculator = OrbitCalculator()

    position = calculator.compute_position(
        eph,
        EPOCH,
    )

    print()
    print(
        f"{SAT_SYSTEM}{SAT_PRN:02d}"
    )

    print(
        f"X = {position.x:15.3f} m"
    )
    print(
        f"Y = {position.y:15.3f} m"
    )
    print(
        f"Z = {position.z:15.3f} m"
    )


if __name__ == "__main__":
    main()