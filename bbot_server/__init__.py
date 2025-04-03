import os

# set up logging
from . import logger

# coverage for tests
if os.getenv("BBOT_TESTING"):
    import coverage

    cov = coverage.process_startup()

from .config import BBOT_SERVER_DIR, BBOT_SERVER_CONFIG

from .interfaces import BBOTServer
