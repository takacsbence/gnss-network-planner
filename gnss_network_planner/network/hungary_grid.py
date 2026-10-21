from pathlib import Path

import numpy as np
import geopandas as gpd
from shapely.geometry import Point


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

    Parameters
    ----------
    spacing_deg : float

        Grid spacing in degrees.

        0.1 deg  -> about 10 km
        0.2 deg  -> about 20 km

    Returns
    -------
    list of tuple

        (latitude_deg, longitude_deg)
    """

    polygon = load_hungary_polygon()

    min_lon, min_lat, max_lon, max_lat = (
        polygon.bounds
    )

    points = []

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

            if polygon.contains(point):
                points.append(
                    np.array([
                        np.radians(lat),
                        np.radians(lon),
                        120.0,
                    ])
                )

    return points

if __name__ == "__main__":

    grid = generate_hungary_grid(
        spacing_deg=0.1
    )

    print(
        f"Grid points: {len(grid)}"
    )

    print(
        grid[:10]
    )