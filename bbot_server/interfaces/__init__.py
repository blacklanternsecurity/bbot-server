import logging

# since each module can contribute custom asset fields, we need to import it before using the interface
from bbot_server import modules  # noqa: F401

log = logging.getLogger("bbot_server.interfaces")


def BBOTServer(interface="python", **kwargs):
    if interface == "python":
        from .python import python

        return python(**kwargs)
    elif interface == "http":
        from .http import http

        return http(**kwargs)
    else:
        raise ValueError(f"Invalid interface: '{interface}' - must be either 'python' or 'http'")
