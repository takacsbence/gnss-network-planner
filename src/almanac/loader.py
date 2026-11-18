
from src.almanac.database import AlmanacDatabase

from src.io.ubx_alm_decoder import (
    iter_almanac_records,
)


def load_almanac(filename: str) -> AlmanacDatabase:

    db = AlmanacDatabase()

    for record in iter_almanac_records(filename):
        db.add(record)

    return db