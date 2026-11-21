
from pathlib import Path

from src.almanac.models import AlmanacRecord


def iter_yuma_records(filename: str):
    """
    Iterate over all almanac records contained in a YUMA file.
    """

    lines = Path(filename).read_text(
        encoding="utf-8"
    ).splitlines()

    block: dict[str, str] = {}

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if line.startswith("ID:"):
            if block:
                yield _parse_block(block)

            block = {}

        if ":" not in line:
            continue

        key, value = line.split(":", 1)

        block[key.strip()] = value.strip()

    if block:
        yield _parse_block(block)


def _parse_block(
    data: dict[str, str],
) -> AlmanacRecord:

    return AlmanacRecord(
        gnss_id="G",
        sv_id=int(data["ID"]),

        week=int(data["week"]),
        toa=float(
            data["Time of Applicability(s)"]
        ),

        af0=float(data["Af0(s)"]),
        af1=float(data["Af1(s/s)"]),

        sqrt_a=float(
            data["SQRT(A)  (m 1/2)"]
        ),

        e=float(data["Eccentricity"]),

        m0=float(
            data["Mean Anom(rad)"]
        ),

        omega=float(
            data["Argument of Perigee(rad)"]
        ),

        omega0=float(
            data["Right Ascen at Week(rad)"]
        ),

        omega_dot=float(
            data["Rate of Right Ascen(r/s)"]
        ),

        i0=float(
            data["Orbital Inclination(rad)"]
        ),

        health=int(data["Health"]),
    )