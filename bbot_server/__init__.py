import uvloop

uvloop.install()

from .config import BBOT_SERVER_DIR, BBOT_SERVER_CONFIG

from .interfaces import BBOTServer
