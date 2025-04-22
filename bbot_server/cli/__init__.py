import signal
from bbot_server.cli import themes

# ignore broken pipe errors when using | head etc.
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

__all__ = ["themes"]
