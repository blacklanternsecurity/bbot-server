def BBOTServer(interface="python", **kwargs):
    if interface == "python":
        from .base import BaseInterface

        return BaseInterface(**kwargs)
    elif interface == "http":
        from .http import http

        return http(**kwargs)
    else:
        raise ValueError(f"Invalid interface: '{interface}' - must be either 'python' or 'http'")
