import os
import logging

# coverage for tests
if os.getenv("BBOT_TESTING"):
    import coverage
    cov = coverage.process_startup()

for root_logger in ("bbot", "bbot_server"):
    logger = logging.getLogger(root_logger)
    logger.setLevel(logging.DEBUG)

from .config import BBOT_SERVER_DIR, BBOT_SERVER_CONFIG

from .interfaces import BBOTServer
