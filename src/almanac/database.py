from src.almanac.models import AlmanacRecord

class AlmanacDatabase:

    def __init__(self):
        self._records: dict[str, AlmanacRecord] = {}

    def add(
        self,
        record: AlmanacRecord,
    ) -> None:

        self._records[record.sat_id] = record

    def get(
        self,
        sat_id: str,
    ) -> AlmanacRecord | None:

        return self._records.get(sat_id)

    def satellite_ids(self) -> list[str]:

        return sorted(self._records.keys())

    def has_satellite(
        self,
        sat_id: str,
    ) -> bool:

        return sat_id in self._records

    def satellites(
        self,
        system: str | None = None,
    ) -> list[str]:

        if system is None:
            return self.satellite_ids()

        return sorted(
            sat_id
            for sat_id in self._records
            if sat_id.startswith(system)
        )