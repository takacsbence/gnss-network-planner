import logging

from datetime import datetime, timezone
import numpy as np
from pathlib import Path

from src.almanac.loader import (
    load_almanac,
)

from src.almanac.orbit_calculator import (
    AlmanacOrbitCalculator,
)
from src.utils.logging_utils import setup_logging
from src.navigation.loader import load_ephemerides
from src.navigation.orbit_calculator import OrbitCalculator
from src.utils.visibility import compute_az_el

logger = logging.getLogger(__name__)

def main():
    setup_logging()

    EPOCH = datetime(
        2026,
        11,
        19,
        12,
        10,
        0,
        tzinfo=timezone.utc,
    )

    RECEIVER_LAT_DEG = 47.0
    RECEIVER_LON_DEG = 19.0
    RECEIVER_H = 120.0

    receiver_llh = np.array([
        np.radians(RECEIVER_LAT_DEG),
        np.radians(RECEIVER_LON_DEG),
        RECEIVER_H,
    ])

    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    calc_alm = AlmanacOrbitCalculator()
    calc_nav = OrbitCalculator()

    # Load almanac

    filename = PROJECT_ROOT / "data" / "almanac" / "assistnow_almanac_20261120.ubx"
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
            / "BRDC00IGS_R_20263230000_01D_MN.rnx"
    )
    db = load_ephemerides(
        NAV_FILE
    )

    logger.info(
        "Loaded %d ephemerides",
        len(db),
    )

    logger.info(
        "%-4s %10s %10s %10s %10s %10s",
        "SAT",
        "DR[km]",
        "AZ_ALM",
        "EL_ALM",
        "AZ_NAV",
        "EL_NAV",
    )

    logger.info("-" * 70)

    for sat_id in alm_db.satellite_ids():
        if sat_id[0] not in {"G", "E", "C", "R"}:
            continue

        alm = alm_db.get(sat_id)

        if alm is None:
            continue

        alm_pos = calc_alm.compute_position(
            alm,
            EPOCH,
        )

        eph = db.get_closest(
            sat_id,
            EPOCH,
        )

        if eph is None:
            continue

        nav_pos = calc_nav.compute_position(
            eph,
            EPOCH,
        )

        alm_az, alm_el = compute_az_el(
            alm_pos.ecef,
            receiver_llh,
        )

        nav_az, nav_el = compute_az_el(
            nav_pos.ecef,
            receiver_llh,
        )

        dr = np.linalg.norm(
            alm_pos.ecef - nav_pos.ecef
        )

        logger.info(
            "%-4s %10.1f %10.1f %10.1f %10.1f %10.1f",
            sat_id,
            dr / 1000.0,
            alm_az,
            alm_el,
            nav_az,
            nav_el,
        )

if __name__ == "__main__":
    main()