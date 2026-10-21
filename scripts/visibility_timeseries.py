import logging

import numpy as np
import pandas as pd

from pathlib import Path
from datetime import datetime, timezone, timedelta

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

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "results"
    / "visibility.csv"
)

VALID_SYSTEMS = {"G", "E", "R", "C"}

START_TIME = datetime(
    2025, 9, 20,
    0, 0, 0,
    tzinfo=timezone.utc,
)

END_TIME = datetime(
    2025, 9, 21,
    0, 0, 0,
    tzinfo=timezone.utc,
)

STEP_SECONDS = 300

MASK_ANGLE_DEG = 10.0

RECEIVER_LAT_DEG = 47.0
RECEIVER_LON_DEG = 19.0
RECEIVER_H = 120.0

receiver_llh = np.array([
    np.radians(RECEIVER_LAT_DEG),
    np.radians(RECEIVER_LON_DEG),
    RECEIVER_H,
])

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

    satellites = [
        sat
        for sat in db.satellites()
        if sat[0] in VALID_SYSTEMS
    ]

    epoch = START_TIME

    calculator = OrbitCalculator()

    results = []

    while epoch <= END_TIME:
        counts = {
            "G": 0,
            "E": 0,
            "R": 0,
            "C": 0,
        }

        for system, sv in satellites:
            eph = db.get_closest(
                system,
                sv,
                epoch,
            )

            if eph is None:
                logger.error(
                    "No ephemeris found for %s%02d %s",
                    system,
                    sv,
                    epoch,
                )

            else:
                sat_position = calculator.compute_position(
                    eph,
                    epoch,
                )

                sat_enu = ecef_to_enu(
                    sat_position.ecef,
                    receiver_llh,
                )

                az, el = azimuth_elevation(
                    sat_enu
                )

                if np.degrees(el) >= MASK_ANGLE_DEG:
                    counts[system] += 1

        results.append({
            "epoch": epoch,
            "gps": counts["G"],
            "galileo": counts["E"],
            "glonass": counts["R"],
            "beidou": counts["C"],
        })

        epoch += timedelta(
            seconds=STEP_SECONDS
        )

    df = pd.DataFrame(
        results
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    logger.info(
        "Computed %d epochs",
        len(results),
    )

    logger.info(
        "Computed %d epochs",
        len(df),
    )

    for constellation in [
        "gps",
        "galileo",
        "glonass",
        "beidou",
    ]:
        logger.info(
            "%-8s avg=%5.2f max=%3d",
            constellation,
            df[constellation].mean(),
            df[constellation].max(),
        )

if __name__ == "__main__":
    main()