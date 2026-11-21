
from src.almanac.database import AlmanacDatabase

from src.io.yuma_decoder import (
    iter_yuma_records,
)


def load_yuma_almanac(
    filename: str,
) -> AlmanacDatabase:
    """
    Load a YUMA almanac file into an AlmanacDatabase.

    Parameters
    ----------
    filename : str
        Path to the YUMA almanac file.

    Returns
    -------
    AlmanacDatabase
        Database containing all almanac records from the file.
    """

    db = AlmanacDatabase()

    for record in iter_yuma_records(filename):
        db.add(record)

    return db