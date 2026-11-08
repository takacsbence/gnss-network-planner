import logging

from datetime import datetime, timezone

from pathlib import Path

from gnss_network_planner.almanac.loader import (
    load_almanac,
)

from gnss_network_planner.almanac.orbit_calculator import (
    AlmanacOrbitCalculator,
)
from gnss_network_planner.utils.logging_utils import setup_logging
from gnss_network_planner.navigation.loader import load_ephemerides
from gnss_network_planner.gnss.orbit_calculator import OrbitCalculator


logger = logging.getLogger(__name__)

def main():
    setup_logging()

    EPOCH = datetime(
        2026,
        10,
        21,
        12,
        0,
        0,
        tzinfo=timezone.utc,
    )

    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    # Load almanac

    filename = PROJECT_ROOT / "data" / "almanac" / "alm.ubx"
    alm_db = load_almanac(filename)

    logger.info(
        "Loaded %d almanac",
        len(alm_db.satellite_ids()),
    )

    # Load navigation
    NAV_FILE = (
            PROJECT_ROOT
            / "data"
            / "navigation"
            / "BRDC00IGS_R_20262940000_01D_MN.rnx"
    )
    db = load_ephemerides(
        NAV_FILE
    )

    logger.info(
        "Loaded %d ephemerides",
        len(db),
    )

    import math

    calc_alm = AlmanacOrbitCalculator()
    calc_nav = OrbitCalculator()

    print()
    print(f"{'SAT':<4} {'DR [m]':>12}")
    print("-" * 20)

    for sat_id in alm_db.satellite_ids():
        if not sat_id.startswith("C"):
            continue

        alm = alm_db.get(sat_id)

        if alm is None:
            continue

        sat_system = sat_id[0]
        sat_prn = int(sat_id[1:])

        eph = db.get_closest(
            sat_system,
            sat_prn,
            EPOCH,
        )

        if eph is None:
            continue

        x_alm, y_alm, z_alm = calc_alm.compute_position(
            alm,
            EPOCH,
        )

        nav_pos = calc_nav.compute_position(
            eph,
            EPOCH,
        )

        dr = math.sqrt(
            (x_alm - nav_pos.x) ** 2 +
            (y_alm - nav_pos.y) ** 2 +
            (z_alm - nav_pos.z) ** 2
        )

        print(
            f"{sat_id:<4} {dr:12.1f}"
        )
    """
    for sat_id in ["E02", "E08"]:
        alm = alm_db.get(sat_id)

        print()
        print("=" * 80)
        print(sat_id)
        print(alm)

        eph = db.get_closest(
            "E",
            int(sat_id[1:]),
            EPOCH,
        )

        print(eph)
    """

if __name__ == "__main__":
    main()