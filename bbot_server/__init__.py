import os

# set up logging
import bbot_server.logger as logger  # noqa: F401

# coverage for tests
if os.getenv("BBOT_TESTING"):
    import coverage

    cov = coverage.process_startup()

from .config import BBOT_SERVER_DIR, BBOT_SERVER_CONFIG

from .interfaces import BBOTServer


__all__ = ["BBOTServer", "BBOT_SERVER_DIR", "BBOT_SERVER_CONFIG"]
