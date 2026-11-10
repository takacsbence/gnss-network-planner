# src/almanac/orbit_calculator.py

import math
from datetime import datetime, timezone

MU_GPS = 3.986005e14
OMEGA_E = 7.2921151467e-5

# --- Időrendszerek -----------------------------------------------------------
GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)
LEAP_GPS_UTC = 18  # GPS-UTC 2017 óta; felülírja az MGA-INI-TIME-UTC, ha van benne
BDT_GPST = 14      # GPST - BDT, másodperc
BDS_WEEK_OFFSET = 1356
GST_WEEK_OFFSET = 1024


def gps_week_tow(t_utc, leap):
    s = (t_utc - GPS_EPOCH).total_seconds() + leap
    w = int(s // 604800)
    return w, s - w * 604800


def full_week(cur_week, wna, modulus):
    """A csonkolt almanach-hétszámból a mostanihoz legközelebbi teljes hét."""
    wa = cur_week - ((cur_week - wna) % modulus)
    if cur_week - wa > modulus // 2:
        wa += modulus
    return wa


class AlmanacOrbitCalculator:

    def compute_position(
        self,
        alm: dict,
        epoch: datetime,
    ) -> tuple[float, float, float]:

        if alm["sys"] == "GLO":
            raise NotImplementedError(
                "GLONASS almanach not yet supported"
            )

        return self._compute_kepler(
            alm,
            epoch,
        )

    def _compute_kepler(
        self,
        alm: dict,
        epoch: datetime,
    ) -> tuple[float, float, float]:

        a = alm["sqrta"] ** 2

        e = alm["e"]

        n = math.sqrt(
            MU_GPS / a**3
        )

        toe = alm["toa"]

        gps_seconds = self._gps_seconds_of_week(
            epoch
        )

        tk = gps_seconds - toe

        #
        # mean anomaly
        #
        M = alm["m0"] + n * tk

        #
        # Kepler
        #
        E = self._solve_kepler(M, e)

        #
        # true anomaly
        #
        v = math.atan2(
            math.sqrt(1 - e * e) * math.sin(E),
            math.cos(E) - e,
        )

        u = v + alm["w"]

        r = a * (1 - e * math.cos(E))

        x_orb = r * math.cos(u)
        y_orb = r * math.sin(u)

        i = alm["i"]

        omega = (
                alm["omega0"]
                + (alm["omegadot"] - OMEGA_E) * tk
                - OMEGA_E * alm["toa"]
        )

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

        return x, y, z

    @staticmethod
    def _solve_kepler(
        M: float,
        e: float,
    ) -> float:

        E = M

        for _ in range(10):
            E = (
                E
                - (E - e * math.sin(E) - M)
                / (1 - e * math.cos(E))
            )

        return E

    @staticmethod
    def _gps_seconds_of_week(
        epoch: datetime,
    ) -> float:

        if epoch.tzinfo is None:
            epoch = epoch.replace(
                tzinfo=timezone.utc
            )

        gps_epoch = datetime(
            1980,
            1,
            6,
            tzinfo=timezone.utc,
        )

        dt = (epoch - gps_epoch).total_seconds()

        return dt % 604800.0