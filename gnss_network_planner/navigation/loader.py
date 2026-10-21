from gnss_network_planner.navigation.models import (
    BroadcastEphemeris,
)

from gnss_network_planner.navigation.database import (
    EphemerisDatabase,
)

from gnss_network_planner.io.rinex_navigation_reader import (
    read_rinex_navigation,
)

def load_ephemerides(
    nav_file: str,
) -> BroadcastEphemeris:
    """
    Load a RINEX navigation file into an EphemerisDatabase.

    The workflow consists of two steps:

    1. Parse the RINEX navigation file.
    2. Store and sort the ephemerides in an EphemerisDatabase.

    Parameters
    ----------
    nav_file : str
        Path to the RINEX navigation file.

    Returns
    -------
    EphemerisDatabase
        Database containing all parsed ephemerides,
        indexed by constellation and PRN.
    """

    # Parse the RINEX navigation file.
    nav = read_rinex_navigation(nav_file)

    # Create an empty ephemeris database.
    db = EphemerisDatabase()

    #get klouchar ionopshere parameters
    alpha, beta = extract_klobuchar_coefficients(nav)
    db.klobuchar_alpha = alpha
    db.klobuchar_beta = beta

    # Convert NavigationData records to lightweight
    # Ephemeris objects used by the positioning engine.
    for eph in nav.records:
        db.add(eph)

    # Sort ephemerides by epoch for efficient
    # time-based retrieval.
    db.sort()

    return db

def extract_klobuchar_coefficients(nav):

    alpha = None
    beta = None

    for corr in nav.header.ionospheric_corrections:

        if corr.system == "GPSA":
            alpha = tuple(corr.coefficients)

        elif corr.system == "GPSB":
            beta = tuple(corr.coefficients)

    return alpha, beta