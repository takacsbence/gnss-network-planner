import numpy as np

def azimuth_elevation(enu):
    """
    Compute azimuth and elevation from an ENU direction vector.

    The input vector typically points from the receiver to the satellite
    and does not need to be normalized.

    Parameters
    ----------
    enu : array-like of shape (3,)
        Local ENU coordinates:

        - East [m]
        - North [m]
        - Up [m]

    Returns
    -------
    np.ndarray of shape (2,)
        Angular coordinates:

        - azimuth [rad]
        - elevation [rad]

    Notes
    -----
    Azimuth is measured clockwise from geographic north:

        - 0°   = North
        - 90°  = East
        - 180° = South
        - 270° = West

    Elevation is measured relative to the local horizon:

        - 0°   = horizon
        - +90° = zenith
        - -90° = nadir

    The returned azimuth is normalized to the range:

        0 <= azimuth < 2π

    For NED coordinates, convert the vector before calling:

        azimuth_elevation([
            ned[1],
            ned[0],
            -ned[2]
        ])
    """

    e, n, u = np.asarray(
        enu,
        dtype=float,
    )

    # Azimuth measured clockwise from north.
    az = np.arctan2(
        e,
        n,
    )

    if az < 0.0:
        az += 2.0 * np.pi

    # Horizontal distance from the local vertical axis.
    horiz_dist = np.hypot(
        e,
        n,
    )

    # Elevation above the local horizon.
    el = np.arctan2(
        u,
        horiz_dist,
    )

    return (
        az,
        el,
    )