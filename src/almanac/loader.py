
from gnss_network_planner.almanac.database import AlmanacDatabase

from gnss_network_planner.io.ubx_alm_decoder import (
    iter_almanac_records,
)


def load_almanac(filename: str) -> AlmanacDatabase:

    db = AlmanacDatabase()

    for record in iter_almanac_records(filename):
        db.add(record)

    return db