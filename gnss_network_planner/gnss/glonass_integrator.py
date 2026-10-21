import math

from gnss_network_planner.utils.constants import *


def derivatives(state, eph):
    """
    Compute the time derivatives of the GLONASS state vector.

    The state vector consists of ECEF position and velocity coordinates:

        state = (x, y, z, vx, vy, vz)

    The acceleration model follows the GLONASS broadcast ephemeris
    definition and includes:

    - Earth's central gravitational force
    - J2 perturbation
    - Earth rotation effects
      (centrifugal and Coriolis terms)
    - Broadcast luni-solar accelerations

    Parameters
    ----------
    state : tuple[float, float, float, float, float, float]
        Satellite position [m] and velocity [m/s] in ECEF coordinates.

    eph : GlonassEphemeris
        GLONASS broadcast ephemeris record.

    Returns
    -------
    tuple[float, float, float, float, float, float]
        Time derivatives:

            (dx/dt, dy/dt, dz/dt,
             dvx/dt, dvy/dt, dvz/dt)
    """

    x, y, z, vx, vy, vz = state

    # Distance from Earth's centre.
    r2 = x * x + y * y + z * z
    r = math.sqrt(r2)

    z2 = z * z
    r5 = r2 * r2 * r

    # J2 perturbation coefficient.
    k = 1.5 * J2 * MU_GLO * AE * AE / r5

    ax = (
        # Central gravitational force
        -MU_GLO * x / r**3

        # J2 perturbation
        -k * x * (1.0 - 5.0 * z2 / r2)

        # Earth rotation terms
        + OMEGA_E_GLO**2 * x
        + 2.0 * OMEGA_E_GLO * vy

        # Broadcast luni-solar acceleration
        + eph.ax * 1000
    )

    ay = (
        -MU_GLO * y / r**3
        - k * y * (1.0 - 5.0 * z2 / r2)
        + OMEGA_E_GLO**2 * y
        - 2.0 * OMEGA_E_GLO * vx
        + eph.ay * 1000
    )

    az = (
        -MU_GLO * z / r**3
        - k * z * (3.0 - 5.0 * z2 / r2)
        + eph.az * 1000
    )

    return (vx, vy, vz, ax, ay, az)


def rk4_step(x, y, z, vx, vy, vz, eph, h):
    """
    Propagate a GLONASS satellite state vector using a single
    fourth-order Runge-Kutta integration step.

    Parameters
    ----------
    x, y, z : float
        ECEF coordinates [m].

    vx, vy, vz : float
        ECEF velocities [m/s].

    eph : GlonassEphemeris
        GLONASS broadcast ephemeris record.

    h : float
        Integration step length [s].

    Returns
    -------
    tuple[float, float, float, float, float, float]
        Updated state vector:

            (x, y, z, vx, vy, vz)
    """

    s = (x, y, z, vx, vy, vz)

    # RK4 stage 1
    k1 = derivatives(s, eph)

    # RK4 stage 2
    s2 = tuple(si + 0.5 * h * ki for si, ki in zip(s, k1))
    k2 = derivatives(s2, eph)

    # RK4 stage 3
    s3 = tuple(si + 0.5 * h * ki for si, ki in zip(s, k2))
    k3 = derivatives(s3, eph)

    # RK4 stage 4
    s4 = tuple(si + h * ki for si, ki in zip(s, k3))
    k4 = derivatives(s4, eph)

    # Weighted RK4 combination
    return tuple(
        si + h / 6.0 * (k1i + 2.0 * k2i + 2.0 * k3i + k4i)
        for si, k1i, k2i, k3i, k4i in zip(s, k1, k2, k3, k4)
    )