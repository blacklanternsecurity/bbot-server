def BBOT_IO(backend="sqlite", **kwargs):
    from bbot_io.interfaces import BBOTInterface

    return BBOTInterface(backend=backend, **kwargs)
