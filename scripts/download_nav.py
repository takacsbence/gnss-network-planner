from datetime import datetime
from pathlib import Path
import logging
import sys

from src.navigation.download_nav_file import (
    download_brdc,
    decompress_gzip,
)
from src.utils.logging_utils import setup_logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def main():
    setup_logging()

    try:
        compressed_nav_file = download_brdc(
            datetime(2026, 10, 21),
            PROJECT_ROOT / "data" / "navigation",
        )

        decompressed_nav_file = decompress_gzip(compressed_nav_file)

        logger.info(
            "Navigation file ready: %s",
            decompressed_nav_file,
        )

    except Exception as exc:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Download failed")
        else:
            logger.error("Download failed: %s", exc)
        sys.exit(1)

if __name__ == "__main__":
    main()