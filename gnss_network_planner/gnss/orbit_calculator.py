import math

from datetime import datetime

from gnss_network_planner.navigation.models import BroadcastEphemeris
from gnss_network_planner.gnss.satellite_position import SatellitePosition
from gnss_network_planner.gnss.glonass_integrator import rk4_step
from gnss_network_planner.utils.constants import *


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
