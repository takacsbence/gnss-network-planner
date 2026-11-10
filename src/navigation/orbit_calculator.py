import math

import numpy as np

from dataclasses import dataclass
from datetime import datetime

from src.navigation.models import BroadcastEphemeris
from src.utils.constants import *

@dataclass
class SatellitePosition:

    gnss_id: str
    sv_id: int

    x: float
    y: float
    z: float

    @property
    def ecef(self):
        return np.array([
            self.x,
            self.y,
            self.z,
        ])

class OrbitCalculator:
    """
    Compute satellite ECEF coordinates from broadcast ephemerides.

    GPS, Galileo and BeiDou satellites use the standard Keplerian
    broadcast orbit model.

    GLONASS satellites use Cartesian state vectors and are propagated
    numerically with a fourth-order Runge-Kutta integrator.
    """

    def compute_position(
            self,
            eph: BroadcastEphemeris,
            epoch: datetime,
    ) -> SatellitePosition:
        """
        Compute satellite position at a given epoch.

        Parameters
        ----------
        eph : BroadcastEphemeris
            Broadcast ephemeris record.

        epoch : datetime
            Requested computation epoch (UTC).

        Returns
        -------
        SatellitePosition
            Satellite ECEF coordinates in metres.
        """

        # ==================================================================
        # GPS / Galileo / BeiDou
        # ==================================================================

        if eph.gnss_id != "R":

            # Time difference from ephemeris reference epoch.
            tk = (
                epoch - eph.time
            ).total_seconds()

            # GPS week rollover correction.
            if tk > 302400:
                tk -= 604800

            if tk < -302400:
                tk += 604800

            # Semi-major axis.
            A = eph.sqrt_a ** 2

            # Corrected mean motion.
            n0 = math.sqrt(MU / A ** 3)
            n = n0 + eph.delta_n

            # Mean anomaly.
            M = eph.m0 + n * tk

            # Solve Kepler equation iteratively.
            E = M

            for _ in range(20):

                dE = (
                    E
                    - eph.e * math.sin(E)
                    - M
                ) / (
                    1.0
                    - eph.e * math.cos(E)
                )

                E -= dE

                if abs(dE) < 1e-12:
                    break

            # True anomaly.
            v = math.atan2(
                math.sqrt(1 - eph.e ** 2) * math.sin(E),
                math.cos(E) - eph.e,
            )

            # Argument of latitude.
            phi = v + eph.omega

            # Harmonic corrections.
            du = (
                eph.cus * math.sin(2 * phi)
                + eph.cuc * math.cos(2 * phi)
            )

            dr = (
                eph.crs * math.sin(2 * phi)
                + eph.crc * math.cos(2 * phi)
            )

            di = (
                eph.cis * math.sin(2 * phi)
                + eph.cic * math.cos(2 * phi)
            )

            # Corrected orbital parameters.
            u = phi + du
            r = A * (1 - eph.e * math.cos(E)) + dr
            i = eph.i0 + di + eph.idot * tk

            # Coordinates in orbital plane.
            x_prime = r * math.cos(u)
            y_prime = r * math.sin(u)

            # Corrected longitude of ascending node.
            Omega = (
                eph.omega0
                + (eph.omega_dot - OMEGA_E) * tk
                - OMEGA_E * eph.toe
            )

            # Transformation from orbital plane to ECEF.
            x = (
                x_prime * math.cos(Omega)
                - y_prime * math.cos(i) * math.sin(Omega)
            )

            y = (
                x_prime * math.sin(Omega)
                + y_prime * math.cos(i) * math.cos(Omega)
            )

            z = (
                y_prime * math.sin(i)
            )

        # ==================================================================
        # GLONASS
        # ==================================================================

        else:

            # Propagation interval in seconds.
            dt = (
                epoch - eph.time
            ).total_seconds()

            # Broadcast coordinates are provided in kilometres.
            x = eph.x * 1000
            y = eph.y * 1000
            z = eph.z * 1000

            vx = eph.vx * 1000
            vy = eph.vy * 1000
            vz = eph.vz * 1000

            # Fixed RK4 integration step.
            rk_step = 60.0

            n = int(abs(dt) // rk_step)
            h = math.copysign(rk_step, dt)

            # Full RK4 steps.
            for _ in range(n):
                x, y, z, vx, vy, vz = rk4_step(
                    x, y, z,
                    vx, vy, vz,
                    eph,
                    h,
                )

            # Final partial step.
            rem = dt - n * h

            if abs(rem) > 1e-9:
                x, y, z, vx, vy, vz = rk4_step(
                    x, y, z,
                    vx, vy, vz,
                    eph,
                    rem,
                )

        return SatellitePosition(
            gnss_id=eph.gnss_id,
            sv_id=eph.sv_id,
            x=x,
            y=y,
            z=z,
        )

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