from pathlib import Path

import pandas as pd

from gnss_network_planner.models.station import (
    Station,
)


def load_stations(
        filename: str | Path,
) -> list[Station]:
    """
    Load monitoring stations from a CSV file.

    Parameters
    ----------
    filename : str or Path
        CSV file containing station definitions.

    Returns
    -------
    list[Station]
        List of Station objects.
    """

    df = pd.read_csv(
        filename,
    )

    stations = []

    for _, row in df.iterrows():

        stations.append(
            Station(
                name=row["name"],
                lat_deg=float(
                    row["lat_deg"]
                ),
                lon_deg=float(
                    row["lon_deg"]
                ),
                h=float(
                    row["h"]
                ),
            )
        )

    return stations
