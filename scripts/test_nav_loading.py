from pathlib import Path
from datetime import datetime, timezone

from gnss_network_planner.navigation.loader import (
    load_ephemerides,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT /
    "data" /
    "nav" /
    "BRDC00IGS_R_20252630000_01D_MN.rnx"
)

some_epoch = datetime(
    2025,
    9,
    20,
    11,
    10,
    0,
    tzinfo=timezone.utc,
)


def main():

    db = load_ephemerides(INPUT_FILE)

    print(f"Ephemerides: {len(db)}")

    satellites = list(db.satellites())

    print(f"Satellites: {len(satellites)}")

    eph = db.get_closest(
        "G",
        1,
        some_epoch,
    )

    print(eph)


if __name__ == "__main__":
    main()