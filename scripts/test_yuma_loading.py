from pathlib import Path

from src.almanac.yuma_loader import (
    load_yuma_almanac,
)


def main():
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    filename = (
        PROJECT_ROOT
        / "data"
        / "almanac"
        / "yuma_20261121.alm"
    )

    db = load_yuma_almanac(filename)

    print(
        len(db.satellite_ids())
    )

    alm = db.get("G02")

    print(alm)
    print(alm.gnss_id)


if __name__ == "__main__":
    main()