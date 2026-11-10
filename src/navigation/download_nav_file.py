from pathlib import Path
from datetime import datetime, timezone
import requests
import gzip
import shutil

import logging

logger = logging.getLogger(__name__)

def day_of_year(date: datetime) -> int:
    return int(date.strftime("%j"))

def build_bkg_url(date: datetime) -> str:

    year = date.year
    doy = day_of_year(date)

    return (
        f"https://igs.bkg.bund.de/root_ftp/IGS/BRDC/"
        f"{year}/{doy:03d}/"
        f"BRDC00IGS_R_{year}{doy:03d}0000_01D_MN.rnx.gz"
    )

def build_epn_url(date: datetime) -> str:

    year = date.year
    doy = day_of_year(date)

    return (
        f"https://epncb.oma.be/pub/RINEX/BRDC/"
        f"{year}/"
        f"BRDC00GOP_R_{year}{doy:03d}0000_01D_MN.rnx.gz"
    )

def download_brdc(date: datetime, output_dir: str | Path) -> Path:

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Downloading BRDC file for YEAR %s DOY %03d",
        date.year,
        day_of_year(date),
    )

    last_exception = None

    DOWNLOAD_SOURCES = [
        (
            "BKG",
            build_bkg_url,
        ),
        (
            "EPN",
            build_epn_url,
        ),
    ]

    for source_name, url_builder in DOWNLOAD_SOURCES:

        url = url_builder(date)

        filename = Path(url).name

        output_file = output_dir / filename

        if output_file.exists():
            logger.info(
                "Using existing navigation file: %s",
                output_file,
            )
            return output_file


        url = url_builder(date)

        logger.debug("Trying : %s", url)

        try:

            response = requests.get(
                url,
                stream=True,
                timeout=30,
            )

            response.raise_for_status()

            logger.debug("Download successful: %s", url)

            with open(output_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return output_file

        except requests.RequestException as exc:

            logger.debug(
                "Server unreachable: %s (%s)",
                url,
                exc,
            )

            last_exception = exc

    raise RuntimeError(
        f"Failed to download navigation file. "
    ) from last_exception

def decompress_gzip(gz_file: Path) -> Path:
    """
    Decompress a .gz file and return the output filename.
    """

    output_file = gz_file.with_suffix("")

    if output_file.exists():
        logger.info("Using existing decompressed file: %s", output_file)
        return output_file

    logger.info("Decompressing: %s", gz_file)

    try:
        with gzip.open(gz_file, "rb") as f_in:
            with open(output_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)


    except OSError as exc:
        raise RuntimeError(
            f"Failed to decompress file: {gz_file}"
        ) from exc

    logger.info("Created: %s", output_file)

    return output_file