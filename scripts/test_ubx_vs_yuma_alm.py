import logging

from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from src.almanac.loader import (
    load_almanac,
)

from src.almanac.yuma_loader import (
    load_yuma_almanac,
)

from src.almanac.orbit_calculator import (
    AlmanacOrbitCalculator,
)

from src.utils.logging_utils import (
    setup_logging,
)

from src.utils.visibility import (
    compute_az_el,
)

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

    calc = AlmanacOrbitCalculator()

    # ------------------------------------------------------------------
    # Load AssistNow UBX almanac
    # ------------------------------------------------------------------

    ubx_file = (
        PROJECT_ROOT
        / "data"
        / "almanac"
        / "assistnow_almanac_20261120.ubx"
    )

    ubx_db = load_almanac(ubx_file)

    logger.info(
        "Loaded %d UBX almanacs",
        len(ubx_db.satellite_ids()),
    )

    # ------------------------------------------------------------------
    # Load YUMA almanac
    # ------------------------------------------------------------------

    yuma_file = (
        PROJECT_ROOT
        / "data"
        / "almanac"
        / "yuma_20261121.alm"
    )

    yuma_db = load_yuma_almanac(yuma_file)

    logger.info(
        "Loaded %d YUMA almanacs",
        len(yuma_db.satellite_ids()),
    )

    logger.info(
        "%-4s %10s %10s %10s",
        "SAT",
        "DR[km]",
        "DAZ[deg]",
        "DEL[deg]",
    )

    logger.info("-" * 50)

    sats = sorted(
        set(ubx_db.satellite_ids())
        & set(yuma_db.satellite_ids())
    )

    for sat_id in sats:

        ubx_alm = ubx_db.get(sat_id)
        yuma_alm = yuma_db.get(sat_id)

        if ubx_alm is None or yuma_alm is None:
            continue

        ubx_pos = calc.compute_position(
            ubx_alm,
            EPOCH,
        )

        yuma_pos = calc.compute_position(
            yuma_alm,
            EPOCH,
        )

        dr = np.linalg.norm(
            ubx_pos.ecef - yuma_pos.ecef
        )

        ubx_az, ubx_el = compute_az_el(
            ubx_pos.ecef,
            receiver_llh,
        )

        yuma_az, yuma_el = compute_az_el(
            yuma_pos.ecef,
            receiver_llh,
        )

        daz = ubx_az - yuma_az

        if daz > 180.0:
            daz -= 360.0

        if daz < -180.0:
            daz += 360.0

        delv = ubx_el - yuma_el

        logger.info(
            "%-4s %10.3f %10.3f %10.3f",
            sat_id,
            dr / 1000.0,
            daz,
            delv,
        )


if __name__ == "__main__":
    main()