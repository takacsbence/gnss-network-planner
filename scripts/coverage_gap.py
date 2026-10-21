import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

from gnss_network_planner.navigation.loader import load_ephemerides
from gnss_network_planner.gnss.orbit_calculator import OrbitCalculator
from gnss_network_planner.gnss.visibility import azimuth_elevation
from gnss_network_planner.utils.coordinates import ecef_to_enu
from gnss_network_planner.utils.logging_utils import setup_logging
from gnss_network_planner.network.hungary_grid import generate_hungary_grid
from gnss_network_planner.models.station import Station
from gnss_network_planner.io.stations import load_stations

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

NAV_FILE = (
    PROJECT_ROOT
    / "data"
    / "nav"
    / "BRDC00IGS_R_20252630000_01D_MN.rnx"
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
    2025, 9, 20,
    0, 0, 0,
    tzinfo=timezone.utc,
)

END_TIME = datetime(
    2025, 9, 21,
    0, 0, 0,
    tzinfo=timezone.utc,
)

STEP_SECONDS = 3600

MASK_ANGLE_DEG = 10.0

VALID_SYSTEMS = {"G", "E", "R", "C"}

def station_llh(
        station: Station,
):
    return np.array([
        np.radians(station.lat_deg),
        np.radians(station.lon_deg),
        station.h,
    ])

def elevation_deg(
        sat_position,
        receiver_llh,
):
    """
    Compute satellite elevation angle.
    """

    enu = ecef_to_enu(
        sat_position.ecef,
        receiver_llh,
    )

    _, elevation = azimuth_elevation(
        enu,
    )

    return np.degrees(
        elevation,
    )


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

    grid = generate_hungary_grid()

    logger.info(
        "Grid points: %d",
        len(grid),
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

            sat_gap_points = []

            visible_grid_points = 0
            uncovered_grid_points = 0

            for point in grid:

                el = elevation_deg(
                    sat_position,
                    point,
                )

                if el >= MASK_ANGLE_DEG:

                    visible_grid_points += 1

                    if not visible_from_monitor:
                        uncovered_grid_points += 1

                        gap_record = {
                            "epoch": epoch.isoformat(),
                            "satellite": f"{system}{sv:02d}",
                            "lat_deg": round(np.degrees(point[0]), 4),
                            "lon_deg": round(np.degrees(point[1]), 4),
                            "elevation_deg": round(el, 1),
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
                    "(visible=%d, uncovered=%d)",
                    system,
                    sv,
                    visible_grid_points,
                    uncovered_grid_points,
                )

            if uncovered_grid_points > 0:
                logger.info(
                    "%s%02d GAP "
                    "(visible=%d uncovered=%d)",
                    system,
                    sv,
                    visible_grid_points,
                    uncovered_grid_points,
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
                epoch_gap_points += uncovered_grid_points

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
    main()