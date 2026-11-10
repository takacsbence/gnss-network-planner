from collections import defaultdict
from datetime import datetime

from gnss_network_planner.almanac.models import AlmanacRecord

"""
class AlmanacDatabase:
    def __init__(self):
        self._records: dict[str, list[AlmanacRecord]] = defaultdict(list)

    def add(self, record: AlmanacRecord) -> None:
        self._records[record.sat_id].append(record)

    def satellite_ids(self) -> list[str]:
        return sorted(self._records.keys())

    def has_satellite(self, sat_id: str) -> bool:
        return sat_id in self._records

    def get_latest(
        self,
        sat_id: str,
        epoch: datetime,
    ) -> AlmanacRecord | None:

        records = self._records.get(sat_id)

        if not records:
            return None

        valid = [
            r
            for r in records
            if r.source_epoch is not None
            and r.source_epoch <= epoch
        ]

        if not valid:
            return None

        return max(
            valid,
            key=lambda r: r.source_epoch,
        )

    def satellites(
        self,
        system: str | None = None,
    ) -> list[str]:

        if system is None:
            return sorted(self._records.keys())

        return sorted(
            sat_id
            for sat_id in self._records
            if sat_id.startswith(system)
        )
"""
from collections import defaultdict


class AlmanacDatabase:

    def __init__(self):
        self._records = {}

    def add(self, record):
        self._records[record["prn"]] = record

    def get(self, sat_id):
        return self._records.get(sat_id)

    def satellite_ids(self):
        return sorted(self._records.keys())