from datetime import datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ALMANAC_DIR = PROJECT_ROOT / "data" / "almanac"
ALMANAC_DIR.mkdir(parents=True, exist_ok=True)

YUMA_URL = (
    "https://celestrak.org/GPS/almanac/Yuma/almanac.yuma.txt"
)


def main():
    response = requests.get(YUMA_URL, timeout=30)
    response.raise_for_status()

    timestamp = datetime.utcnow().strftime("%Y%m%d")

    output_file = (
        ALMANAC_DIR /
        f"yuma_{timestamp}.alm"
    )

    output_file.write_text(
        response.text,
        encoding="utf-8",
    )

    print(f"Saved YUMA almanac to: {output_file}")


if __name__ == "__main__":
    main()