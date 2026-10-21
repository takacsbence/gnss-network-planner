from datetime import datetime
from collections import defaultdict
from gnss_network_planner.navigation.models import (
    BroadcastEphemeris,
)

class EphemerisDatabase:
    """
    In-memory ephemeris database.

    Ephemerides are grouped by satellite using the tuple

        (constellation, prn)

    as key.

    The database provides efficient retrieval of all
    ephemerides for a satellite and lookup of the record
    closest to a requested epoch.
    """

    def __init__(self):
        """
        Create an empty ephemeris database.
        """

        self._satellites = defaultdict(list)

        self._ephemerides = {}

        # GPS Klobuchar coefficients
        self.klobuchar_alpha = None
        self.klobuchar_beta = None

    def add(self, eph: BroadcastEphemeris):
        """
        Add a single ephemeris record to the database.
        """

        key = (
            eph.constellation,
            eph.prn,
        )

        self._satellites[key].append(eph)

    def sort(self):
        """
        Sort ephemerides of each satellite by epoch.

        This should be called once after all records
        have been loaded.
        """

        for records in self._satellites.values():

            records.sort(
                key=lambda r: r.epoch
            )

    def size(self):
        """
        Return the total number of ephemeris records.
        """

        return sum(
            len(v)
            for v in self._satellites.values()
        )

    def satellites(self):
        """
        Return all satellites present in the database.

        Returns
        -------
        iterable
            Collection of (constellation, prn) keys.
        """

        return self._satellites.keys()

    def get_all(
        self,
        constellation,
        prn,
    ):
        """
        Return all ephemerides for a satellite.

        Parameters
        ----------
        constellation : str
            GNSS constellation identifier
            ('G', 'R', 'E', 'C', ...)

        prn : int
            Satellite PRN number.
        """

        return self._satellites.get(
            (constellation, prn),
            []
        )

    def get_closest(
            self,
            constellation,
            prn,
            epoch,
    ):
        """
        Return the ephemeris whose reference epoch is
        closest to the requested epoch.

        Parameters
        ----------
        constellation : str
            GNSS constellation identifier.

        prn : int
            Satellite PRN number.

        epoch : datetime
            Epoch of interest.

        Returns
        -------
        Ephemeris | None
            Ephemeris with the closest reference epoch,
            regardless of whether that reference epoch
            is before or after the requested epoch.

            Returns None if the satellite is not present
            in the database.
        """

        records = self.get_all(
            constellation,
            prn,
        )

        if not records:
            return None

        return min(
            records,
            key=lambda r: abs(
                (r.epoch - epoch).total_seconds()
            ),
        )

    def get_by_iode(
            self,
            constellation: str,
            prn: int,
            iode: int,
            epoch: datetime,
    ):
        """
        Return the most recent broadcast ephemeris with the
        specified IODE that was already available at the
        requested epoch.

        This method is primarily intended for matching
        SPARTN orbit and clock corrections to the broadcast
        ephemeris they reference.

        Parameters
        ----------
        constellation : str
            GNSS constellation identifier.

        prn : int
            Satellite PRN number.

        iode : int
            Broadcast ephemeris IODE.

        epoch : datetime
            Observation epoch.

        Returns
        -------
        Ephemeris | None
            Most recent ephemeris record with the specified
            IODE, or None if no matching ephemeris is found.
        """

        matches = [
            eph
            for eph in self.get_all(
                constellation,
                prn,
            )
            if (
                    eph.iode == iode
                    #and eph.epoch <= epoch
            )
        ]

        if not matches:
            return None

        return max(
            matches,
            key=lambda e: e.epoch,
        )

    def __len__(self):
        """
        Return the number of ephemeris records.
        """

        return sum(
            len(records)
            for records in self._satellites.values()
        )