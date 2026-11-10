from pathlib import Path

from src.almanac.loader import (
    load_almanac,
)


def main():
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    filename = PROJECT_ROOT / "data" / "almanac" / "alm.ubx"
    db = load_almanac(filename)

    print(
        len(db.satellite_ids())
    )

    alm = db.get("G01")

    print(alm)


if __name__ == "__main__":
    main()