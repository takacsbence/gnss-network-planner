import numpy as np
import geopandas as gpd

from pathlib import Path
from shapely.geometry import Point

from src.utils.coordinates import (
    geodetic_to_ecef,
    rot_enu,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

COUNTRIES_FILE = (
    PROJECT_ROOT
    / "data"
    / "boundaries"
    / "ne_10m_admin_0_countries.shp"
)


def load_hungary_polygon():
    """
    Load Hungary polygon from a Natural Earth shapefile.
    """

    countries = gpd.read_file(
        COUNTRIES_FILE
    )

    hungary = countries[
        countries["NAME"] == "Hungary"
    ]

    if len(hungary) != 1:
        raise RuntimeError(
            "Hungary polygon not found."
        )

    return hungary.iloc[0].geometry


def generate_hungary_grid(
        spacing_deg=0.1,
):
    """
    Generate grid points inside Hungary.

    Returns
    -------
    grid_llh : ndarray (N,3)
        Latitude [rad], longitude [rad], height [m]

    grid_ecef : ndarray (N,3)
        ECEF coordinates [m]

    grid_rot : ndarray (N,3,3)
        ENU rotation matrices
    """

    polygon = load_hungary_polygon()

    min_lon, min_lat, max_lon, max_lat = (
        polygon.bounds
    )

    grid_llh = []
    grid_ecef = []
    grid_rot = []

    latitudes = np.arange(
        min_lat,
        max_lat + spacing_deg,
        spacing_deg,
    )

    longitudes = np.arange(
        min_lon,
        max_lon + spacing_deg,
        spacing_deg,
    )

    for lat in latitudes:

        for lon in longitudes:

            point = Point(
                lon,
                lat,
            )

            if not polygon.contains(point):
                continue

            llh = np.array([
                np.radians(lat),
                np.radians(lon),
                120.0,
            ])

            ecef = geodetic_to_ecef(
                llh
            )

            R = rot_enu(
                llh
            )

            grid_llh.append(
                llh
            )

            grid_ecef.append(
                ecef
            )

            grid_rot.append(
                R
            )

    return (
        np.asarray(grid_llh),
        np.asarray(grid_ecef),
        np.asarray(grid_rot),
    )


if __name__ == "__main__":

    llh, ecef, rot = generate_hungary_grid(
        spacing_deg=0.1
    )

    print(
        f"Grid points: {len(llh)}"
    )

    print(
        "LLH shape:",
        llh.shape
    )

    print(
        "ECEF shape:",
        ecef.shape
    )

    print(
        "ROT shape:",
        rot.shape
    )
