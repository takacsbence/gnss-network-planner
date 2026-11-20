from pathlib import Path
import os

import requests
from dotenv import load_dotenv

from datetime import datetime

timestamp = datetime.now().strftime("%Y%m%d")

ZTP_URL = (
    "https://api.thingstream.io/ztp/assistnow/credentials"
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ALM_FILE = (
    PROJECT_ROOT
    / "data"
    / "almanac"
    / f"assistnow_almanac_{timestamp}.ubx"
)

def get_chipcode(
    token: str,
) -> tuple[str, str]:
    """
    Request an AssistNow chipcode via ZTP.
    """

    payload = {
        "token": token,
        "messages": {
            "UBX-SEC-UNIQID": os.getenv(
                "UBX_SEC_UNIQID_HEX"
            ),
            "UBX-MON-VER": os.getenv(
                "UBX_MON_VER_HEX"
            ),
        },
    }

    response = requests.post(
        ZTP_URL,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    return (
        data["chipcode"],
        data["serviceUrl"],
    )


def main():
    load_dotenv()

    token = os.getenv(
        "THINGSTREAM_ZTP_TOKEN",
    )

    if not token:
        raise RuntimeError(
            "THINGSTREAM_ZTP_TOKEN environment variable not set."
        )

    chipcode, service_url = get_chipcode(
        token,
    )

    print(
        "Obtained AssistNow chipcode."
    )

    params = {
        "chipcode": chipcode,
        "data": "ualm",
        "gnss": "gps,gal,glo,bds,qzss",
    }

    response = requests.get(
        service_url,
        params=params,
        timeout=60,
    )

    response.raise_for_status()

    ALM_FILE.write_bytes(
        response.content,
    )

    print(
        f"Downloaded {len(response.content)} bytes "
        f"to {ALM_FILE}"
    )


if __name__ == "__main__":
    main()