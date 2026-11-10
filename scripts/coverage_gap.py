import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

from src.navigation.loader import load_ephemerides
from src.navigation.orbit_calculator import OrbitCalculator
from src.utils.logging_utils import setup_logging
from src.network.hungary_grid import generate_hungary_grid
from src.io.stations import load_stations
from src.utils.visibility import elevation_deg


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

NAV_FILE = (
    PROJECT_ROOT
    / "data"
    / "navigation"
    / "BRDC00IGS_R_20262940000_01D_MN.rnx"
)

DETAIL_FILE = (
    PROJECT_ROOT
    / "data"
    / "results"
    / "coverage_gap_points.csv"
)

STATION_FILE = (
    PROJECT_ROOT
    / "data"
    / "stations"
    / "monitor_network.csv"
)

EPOCH_FILE = (
    PROJECT_ROOT
    / "data"
    / "results"
    / "coverage_gap_epochs.csv"
)

START_TIME = datetime(
    2026, 10, 21,
    0, 0, 0,
    tzinfo=timezone.utc,
)

END_TIME = datetime(
    2026, 10, 21,
    23, 59, 59,
    tzinfo=timezone.utc,
)

STEP_SECONDS = 600

MASK_ANGLE_DEG = 10.0

VALID_SYSTEMS = {"G", "E", "R", "C"}


def main():

    setup_logging()

    logger.info("Loading navigation file")

    db = load_ephemerides(
        NAV_FILE,
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

    logger.info(
        "Satellites: %d",
        len(satellites),
    )

    grid_llh, grid_ecef, grid_rot = (
        generate_hungary_grid()
    )

    logger.info(
        "Grid points: %d",
        len(grid_llh),
    )

    # ----------------------------------------------------------------------
    # Monitor stations
    # ----------------------------------------------------------------------

    monitor_stations = load_stations(
        STATION_FILE,
    )

    logger.info(
        "Loaded %d monitor stations",
        len(monitor_stations),
    )

    calculator = OrbitCalculator()

    all_gap_points = []

    epoch = START_TIME

    epoch_results = []

    while epoch <= END_TIME:
        epoch_gap_satellites = 0
        epoch_gap_points = 0

        for system, sv in satellites:

            eph = db.get_closest(
                system,
                sv,
                epoch,
            )

            if eph is None:
                continue

            sat_position = calculator.compute_position(
                eph,
                epoch,
            )

            visible_from_monitor = False

            station_elevations = {}

            for station in monitor_stations:

                el = elevation_deg(
                    sat_position,
                    station.llh,
                )

                station_elevations[
                    station.name
                ] = round(el, 1)

                if el >= MASK_ANGLE_DEG:
                    visible_from_monitor = True

            if visible_from_monitor:
                continue


            sat_xyz = sat_position.ecef

            diff = sat_xyz - grid_ecef

            enu = np.einsum(
                "nij,nj->ni",
                grid_rot,
                diff,
            )

            horizontal = np.hypot(
                enu[:, 0],
                enu[:, 1],
            )

            elevation_deg_array = np.degrees(
                np.arctan2(
                    enu[:, 2],
                    horizontal,
                )
            )

            visible_mask = (
                    elevation_deg_array
                    >= MASK_ANGLE_DEG
            )

            visible_indices = np.where(
                visible_mask
            )[0]

            gap_points = len(
                visible_indices
            )

            sat_gap_points = []

            for idx in visible_indices:
                gap_record = {
                    "epoch": epoch.isoformat(),
                    "satellite": f"{system}{sv:02d}",
                    "lat_deg": round(
                        np.degrees(
                            grid_llh[idx, 0]
                        ),
                        4,
                    ),
                    "lon_deg": round(
                        np.degrees(
                            grid_llh[idx, 1]
                        ),
                        4,
                    ),
                    "elevation_deg": round(
                        elevation_deg_array[idx],
                        1,
                    ),
                }

                sat_gap_points.append(
                    gap_record
                )

                all_gap_points.append(
                    gap_record
                )

            if sat_gap_points:

                logger.info(
                    "%s%02d GAP "
                    "(uncovered=%d)",
                    system,
                    sv,
                    gap_points,
                )

                elevation_text = ", ".join(
                    f"{name}={elevation:.1f}°"
                    for name, elevation
                    in station_elevations.items()
                )

                logger.info(
                    "%s%02d station elevations: %s",
                    system,
                    sv,
                    elevation_text,
                )

                epoch_gap_satellites += 1
                epoch_gap_points += gap_points

        logger.info(
            "%s gaps: satellites=%d points=%d",
            epoch.isoformat(),
            epoch_gap_satellites,
            epoch_gap_points,
        )

        epoch_results.append(
            {
                "epoch": epoch,
                "gap_satellites": epoch_gap_satellites,
                "gap_points": epoch_gap_points,
            }
        )

        epoch += timedelta(
            seconds=STEP_SECONDS
        )


    pd.DataFrame(
        all_gap_points
    ).to_csv(
        DETAIL_FILE,
        index=False,
    )

    logger.info(
        "Gap points written to %s",
        DETAIL_FILE,
    )

    pd.DataFrame(
        epoch_results
    ).to_csv(
        EPOCH_FILE,
        index=False,
    )


if __name__ == "__main__":
    import cProfile
    import pstats

    profiler = cProfile.Profile()
    profiler.enable()

    main()

    profiler.disable()

    stats = pstats.Stats(profiler)
    stats.sort_stats("cumtime")
    stats.print_stats(30)