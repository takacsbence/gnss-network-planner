import logging

import numpy as np

from pathlib import Path
from datetime import datetime, timezone

from gnss_network_planner.navigation.loader import load_ephemerides
from gnss_network_planner.gnss.orbit_calculator import OrbitCalculator
from gnss_network_planner.utils.logging_utils import setup_logging
from gnss_network_planner.utils.coordinates import ecef_to_enu
from gnss_network_planner.gnss.visibility import azimuth_elevation

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

RECEIVER_LAT_DEG = 47.4979
RECEIVER_LON_DEG = 19.0402
RECEIVER_H = 120.0

receiver_llh = np.array([
    np.radians(RECEIVER_LAT_DEG),
    np.radians(RECEIVER_LON_DEG),
    RECEIVER_H,
])

SAT_SYSTEM = "C"
SAT_PRN = 25

def main():
    setup_logging()
    logger.info("GNSS Network Planner started")

    db = load_ephemerides(
        NAV_FILE
    )

    logger.info(
        "Loaded %d ephemerides",
        len(db),
    )

    eph = db.get_closest(
        SAT_SYSTEM,
        SAT_PRN,
        EPOCH,
    )

    if eph is None:
        logger.error(
            "No ephemeris found for %s%02d",
            SAT_SYSTEM,
            SAT_PRN,
        )
        return

    logger.info(
        "Selected ephemeris: %s%02d (TOE=%s)",
        SAT_SYSTEM,
        SAT_PRN,
        eph.epoch

    )

    calculator = OrbitCalculator()

    sat_position = calculator.compute_position(
        eph,
        EPOCH,
    )

    logger.info(
        "Satellite position (%s%02d) X = %15.3f m Y = %15.3f m Z = %15.3f m",
        SAT_SYSTEM,
        SAT_PRN,
        sat_position.x,
        sat_position.y,
        sat_position.z,
    )

    sat_enu = ecef_to_enu(
        sat_position.ecef,
        receiver_llh,
    )

    azimuth, elevation = azimuth_elevation(
        sat_enu
    )

    logger.info(
        "Azimuth   : %.1f deg Elevation : %.1f deg",
        np.degrees(azimuth),
        np.degrees(elevation),
    )


if __name__ == "__main__":
    main()