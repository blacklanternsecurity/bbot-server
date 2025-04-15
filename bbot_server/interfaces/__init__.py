import logging

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
