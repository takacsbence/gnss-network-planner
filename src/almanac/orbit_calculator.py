import math

from datetime import datetime, timezone, timedelta

from src.navigation.orbit_calculator import SatellitePosition
from src.almanac.models import AlmanacRecord
from src.utils.time_utils import (
    datetime_to_gps_time,
    resolve_full_week,
    BDT_GPST_OFFSET,
    BDS_WEEK_OFFSET,
    GST_WEEK_OFFSET,
    SECONDS_PER_WEEK,
)

from src.utils.constants import (
    MU,
    MU_GLO,
    PI,
    AE,
    J2,
    OMEGA_E,
    OMEGA_E_GLO,
)

class AlmanacOrbitCalculator:
    """
    Satellite position computation from GNSS almanac data.

    Supports:
        - GPS almanacs
        - Galileo almanacs
        - BeiDou almanacs
        - GLONASS almanacs

    For GPS, Galileo and BeiDou satellites, positions are computed from
    Keplerian orbital elements contained in the almanac.

    For GLONASS satellites, positions are computed using the dedicated
    GLONASS almanac model defined in the GLONASS ICD.
    """
    def compute_position(
        self,
        alm: AlmanacRecord,
        epoch: datetime,
    ) -> SatellitePosition:
        """
        Compute ECEF satellite coordinates for the requested epoch.

        Parameters
        ----------
        alm : AlmanacRecord
            Decoded almanac record.
        epoch : datetime
            Target epoch in GPS time.

        Returns
        -------
        SatellitePosition
            Satellite ECEF position in meters.
        """
        if alm.gnss_id == "R":
            return self._pos_glo(
                alm,
                epoch,
            )
        else:
            return self._compute_kepler(
                alm,
                epoch,
            )

    def _compute_tk(
            self,
            alm: AlmanacRecord,
            epoch: datetime,
    ) -> float:
        """
        Compute the elapsed time between the almanac reference epoch
        (TOA) and the requested epoch.

        The method reconstructs the full almanac week number from the
        truncated week transmitted in the almanac and derives the
        corresponding time difference in seconds.

        Returns
        -------
        float
            Time difference tk [s].
        """

        gw, gtow = datetime_to_gps_time(epoch)

        if alm.gnss_id == "G":
            cw, tow, mod = gw, gtow, 256
        elif alm.gnss_id == "E":
            cw, tow, mod = gw - GST_WEEK_OFFSET, gtow, 4
        elif alm.gnss_id == "C":
            bs = gw * SECONDS_PER_WEEK + gtow - BDT_GPST_OFFSET
            cw, tow, mod = int(bs // SECONDS_PER_WEEK) - BDS_WEEK_OFFSET, bs % SECONDS_PER_WEEK, 256
        else:
            raise ValueError(
                f"Unsupported GNSS: {alm.gnss_id}"
            )

        wa = resolve_full_week(cw, alm.week, mod)

        tk = (cw - wa) * SECONDS_PER_WEEK + (tow - alm.toa)

        return tk

    def _compute_kepler(
        self,
        alm: AlmanacRecord,
        epoch: datetime,
    ) -> SatellitePosition:
        """
        Compute satellite position from broadcast almanac Keplerian
        orbital elements.

        Applicable to GPS, Galileo and BeiDou satellites.
        """

        a = alm.sqrt_a ** 2
        e = alm.e
        # Mean motion.
        n = math.sqrt(MU / a**3)

        tk = self._compute_tk(alm, epoch)
        #print("tk = ", tk, alm["toa"], alm["prn"], alm["wna"])

        # Mean anomaly.
        M = alm.m0 + n * tk

        # Solve Kepler's equation.
        E = self._solve_kepler(M, e)

        # True anomaly.
        v = math.atan2(
            math.sqrt(1 - e * e) * math.sin(E),
            math.cos(E) - e,
        )

        # Argument of latitude.
        u = v + alm.omega

        # Orbital radius.
        r = a * (1 - e * math.cos(E))

        # Position in orbital plane.
        x_orb = r * math.cos(u)
        y_orb = r * math.sin(u)

        i = alm.i0

        # Corrected longitude of ascending node.
        omega = (
                alm.omega0
                + (alm.omega_dot - OMEGA_E) * tk
                - OMEGA_E * alm.toa
        )

        # Transform from orbital plane to ECEF.
        x = (
            x_orb * math.cos(omega)
            - y_orb * math.cos(i) * math.sin(omega)
        )

        y = (
            x_orb * math.sin(omega)
            + y_orb * math.cos(i) * math.cos(omega)
        )

        z = (
            y_orb * math.sin(i)
        )

        #print(epoch, "alm tk = ", tk, "toa = ", alm["toa"], "a =", a, e, "n = ", n, "M0 [deg]= ", np.degrees(alm["m0"]), "r = ", r, "x = ", x_orb, "y = ", y_orb, i, omega, "X = ", x, "Y = ", y, "Z = ", z)

        return SatellitePosition(
            gnss_id=alm.gnss_id,
            sv_id=alm.sv_id,
            x=x,
            y=y,
            z=z,
        )

    @staticmethod
    def _solve_kepler(
        M: float,
        e: float,
    ) -> float:
        """
        Solve Kepler's equation using Newton-Raphson iteration.

        Parameters
        ----------
        M : float
            Mean anomaly [rad].
        e : float
            Orbital eccentricity.

        Returns
        -------
        float
            Eccentric anomaly [rad].
        """

        E = M

        for _ in range(10):
            E = (
                E
                - (E - e * math.sin(E) - M)
                / (1 - e * math.cos(E))
            )

        return E


    def _glo_epoch(
        self,
        N,
        epoch
    ):
        """
        Determine the GPS-time epoch corresponding to the GLONASS almanac
        day number N.

        The GLONASS almanac day belongs to a four-year cycle. The cycle
        closest to the requested epoch is selected.
        """

        best = None

        for leap_year in range(epoch.year - 8, epoch.year + 5):
            if leap_year % 4:
                continue

            d = datetime(leap_year, 1, 1, tzinfo=timezone.utc) + timedelta(days=N - 1) - timedelta(hours=3)

            if best is None or abs((d - epoch).total_seconds()) < abs((best - epoch).total_seconds()):
                best = d

        return best


    def _pos_glo(
        self,
        alm: AlmanacRecord,
        epoch: datetime,
    ):
        """
        Compute GLONASS satellite position from almanac parameters.

        References
        ----------
        GLONASS ICD, Appendix describing the analytical almanac orbit model.

        The implementation follows the analytical GLONASS almanac orbit
        model including J2 perturbation terms.
        """

        t0 = self._glo_epoch(alm.glonass_n, epoch) + timedelta(seconds=alm.tlam)

        dt = (epoch - t0).total_seconds()

        # Reference inclination plus transmitted correction.
        i = (63 / 180) * PI + alm.di

        Tav = 43200 + alm.dT

        # Number of completed draconitic revolutions.
        W = math.floor(dt / Tav)

        Tdr = Tav + (2 * W + 1) * alm.dTdot

        n = 2 * PI / Tdr

        e = alm.e
        w0 = alm.omega0

        # Iteratively determine semi-major axis from draconitic period.
        aa = (Tdr / (2 * PI)) ** (2 / 3) * MU_GLO ** (1 / 3)

        for _ in range(20):
            p = aa * (1 - e ** 2)

            k = 1.5 * J2 * (AE / p) ** 2

            Tosk = Tdr / (1 - k * ((2 - 2.5 * math.sin(i) ** 2) * (1 - e ** 2) ** 1.5 /
                                   (1 + e * math.cos(w0)) ** 2 +
                                   (1 + e * math.cos(w0)) ** 3 / (1 - e ** 2)))

            new = (Tosk / (2 * PI)) ** (2 / 3) * MU_GLO ** (1 / 3)

            if abs(new - aa) < 1e-3:
                aa = new
                break

            aa = new

        p = aa * (1 - e ** 2)

        # J2 secular perturbations.
        Omdot = -1.5 * J2 * n * (AE / p) ** 2 * math.cos(i)

        wdot = -0.75 * J2 * n * (AE / p) ** 2 * (1 - 5 * math.cos(i) ** 2)

        lam = alm.lam + (Omdot - OMEGA_E_GLO) * dt
        w = w0 + wdot * dt

        # Mean argument of latitude.
        E0 = -2 * math.atan(math.sqrt((1 - e) / (1 + e)) * math.tan(w0 / 2))

        L1 = w0 + E0 - e * math.sin(E0)

        L2 = L1 + n * (dt - (W * Tav + alm.dTdot * W ** 2))

        M = L2 - w

        E = self._solve_kepler(M, e)

        nu = math.atan2(math.sqrt(1 - e ** 2) * math.sin(E), math.cos(E) - e)

        u = nu + w

        r = aa * (1 - e * math.cos(E))

        # Convert orbital-plane coordinates to ECEF.
        x = r * (math.cos(lam) * math.cos(u) - math.sin(lam) * math.sin(u) * math.cos(i))
        y = r * (math.sin(lam) * math.cos(u) + math.cos(lam) * math.sin(u) * math.cos(i))
        z = r * math.sin(u) * math.sin(i)

        return SatellitePosition(
            gnss_id=alm.gnss_id,
            sv_id=alm.sv_id,
            x=x,
            y=y,
            z=z,
        )

