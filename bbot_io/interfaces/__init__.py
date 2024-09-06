def BBOTInterface(backend="sqlite", **kwargs):
    backend = backend.strip().lower()
    if backend == "rest":
        from bbot_io.interfaces.rest import RestInterface

        # we don't actually use sqlite here, this used only for metadata
        return RestInterface("sqlite", **kwargs)

    else:
        from bbot_io.interfaces._base import BaseInterface

        return BaseInterface(backend, **kwargs)
