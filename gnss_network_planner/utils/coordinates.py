import numpy as np

from gnss_network_planner.utils.constants import *

def ecef_to_geodetic(
        ecef,
        tol=1e-12,
        max_iter=20,
):
    """
    Convert ECEF coordinates to WGS84 geodetic coordinates.

    The conversion is performed using an iterative latitude refinement
    method (Bowring / Hofmann-Wellenhof approach). Starting from an
    initial latitude estimate, the solution is iteratively improved
    until the latitude change falls below the specified tolerance.

    In practice, convergence is typically achieved within 3-5 iterations.

    Parameters
    ----------
    ecef : array-like of shape (3,)
        ECEF coordinates [X, Y, Z] in metres.

    tol : float, optional
        Convergence threshold for latitude updates [rad].

    max_iter : int, optional
        Maximum number of iterations.

    Returns
    -------
    np.ndarray of shape (3,)
        Geodetic coordinates:

        - latitude [rad]
        - longitude [rad]
        - ellipsoidal height [m]
    """

    x, y, z = np.asarray(ecef, dtype=float)

    a = WGS84_A
    e2 = WGS84_E2

    # Distance from the Earth rotation axis.
    p = np.hypot(x, y)

    # Geodetic longitude.
    lon = np.arctan2(y, x)

    # Initial latitude estimate assuming h = 0.
    lat = np.arctan2(
        z,
        p * (1.0 - e2),
    )

    for _ in range(max_iter):

        # Radius of curvature in the prime vertical.
        N = a / np.sqrt(
            1.0 - e2 * np.sin(lat) ** 2
        )

        # Ellipsoidal height.
        h = p / np.cos(lat) - N

        # Updated latitude estimate.
        lat_new = np.arctan2(
            z,
            p * (
                1.0
                - e2 * N / (N + h)
            ),
        )

        if abs(lat_new - lat) < tol:
            lat = lat_new
            break

        lat = lat_new

    # Final height computation.
    N = a / np.sqrt(
        1.0 - e2 * np.sin(lat) ** 2
    )

    h = p / np.cos(lat) - N

    return np.array([
        lat,
        lon,
        h,
    ])


def geodetic_to_ecef(llh):
    """
    Convert WGS84 geodetic coordinates to ECEF coordinates.

    Parameters
    ----------
    llh : array-like of shape (3,)
        Geodetic coordinates:

        - latitude [rad]
        - longitude [rad]
        - ellipsoidal height [m]

    Returns
    -------
    np.ndarray of shape (3,)
        ECEF coordinates:

        - X [m]
        - Y [m]
        - Z [m]

    Notes
    -----
    Uses the WGS84 reference ellipsoid defined by:

        - semi-major axis (WGS84_A)
        - first eccentricity squared (WGS84_E2)

    The conversion follows the standard geodetic-to-ECEF transformation.
    """

    lat, lon, h = np.asarray(llh, dtype=float)

    a = WGS84_A
    e2 = WGS84_E2

    # Radius of curvature in the prime vertical.
    N = a / np.sqrt(
        1.0 - e2 * np.sin(lat) ** 2
    )

    # ECEF coordinates.
    x = (
            (N + h)
            * np.cos(lat)
            * np.cos(lon)
    )

    y = (
            (N + h)
            * np.cos(lat)
            * np.sin(lon)
    )

    z = (
            (N * (1.0 - e2) + h)
            * np.sin(lat)
    )

    return np.array([
        x,
        y,
        z,
    ])

def rot_enu(
        llh_ref,
        degrees=False,
):
    """
    Construct the ECEF-to-ENU rotation matrix.

    The returned matrix transforms a vector expressed in the ECEF frame
    into the local East-North-Up (ENU) frame centred at the reference
    location.

    The transformation is applied as:

        enu = rot_enu(llh_ref) @ (ecef - ecef_ref)

    Parameters
    ----------
    llh_ref : array-like of shape (3,)
        Reference geodetic coordinates:

        - latitude [rad]
        - longitude [rad]
        - ellipsoidal height [m]

        Only latitude and longitude are used when constructing the
        rotation matrix.

    degrees : bool, optional
        If True, latitude and longitude are interpreted in degrees.
        Default is False (radians).

    Returns
    -------
    np.ndarray of shape (3, 3)
        Rotation matrix transforming ECEF vectors into the local
        ENU frame.

    Notes
    -----
    The ENU coordinate axes are defined as:

    - East: tangent to the parallel
    - North: tangent to the meridian
    - Up: normal to the reference ellipsoid
    """

    lat, lon, _ = np.asarray(
        llh_ref,
        dtype=float,
    )

    if degrees:
        lat, lon = np.radians(
            [lat, lon]
        )

    sl = np.sin(lat)
    cl = np.cos(lat)

    so = np.sin(lon)
    co = np.cos(lon)

    return np.array([
        [-so,        co,       0.0],
        [-sl * co, -sl * so,   cl],
        [ cl * co,  cl * so,   sl],
    ])

def ecef_to_enu(
        ecef,
        llh_ref,
):
    """
    Convert an ECEF position to local ENU coordinates.

    The ENU (East-North-Up) vector is expressed relative to a reference
    position defined by geodetic latitude, longitude and height.

    Parameters
    ----------
    ecef : array-like of shape (3,)
        ECEF coordinates [X, Y, Z] in metres.

    llh_ref : array-like of shape (3,)
        Reference geodetic coordinates:

        - latitude [rad]
        - longitude [rad]
        - ellipsoidal height [m]

    Returns
    -------
    np.ndarray of shape (3,)
        Local ENU coordinates relative to the reference point:

        - East [m]
        - North [m]
        - Up [m]

    Notes
    -----
    The function first computes the ECEF coordinates of the reference
    position, then forms the difference vector and rotates it into the
    local ENU frame.
    """

    # Reference position in ECEF.
    ecef_ref = geodetic_to_ecef(llh_ref)

    # Relative vector from reference point to target position.
    d_ecef = (
        np.asarray(ecef, dtype=float)
        - ecef_ref
    )

    # Transform ECEF vector into the local ENU frame.
    return rot_enu(llh_ref) @ d_ecef