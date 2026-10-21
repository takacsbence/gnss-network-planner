from gnss_network_planner.utils.logging_utils import setup_logging

import logging

logger = logging.getLogger(__name__)

def main():
    setup_logging()
    logger.info("GNSS Network Planner started")

if __name__ == "__main__":
    main()