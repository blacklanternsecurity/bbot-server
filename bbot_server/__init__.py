def BBOT_IO(backend="sqlite", **kwargs):
    from bbot_server.interfaces import BBOTInterface

    return BBOTInterface(backend=backend, **kwargs)
