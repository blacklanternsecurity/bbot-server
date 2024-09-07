def BBOTInterface(backend="sqlite", **kwargs):
    backend = backend.strip().lower()
    if backend == "http":
        from bbot_io.interfaces.http import HTTPInterface

        # we don't actually use sqlite here, this used only for metadata
        return HTTPInterface("sqlite", **kwargs)

    else:
        from bbot_io.interfaces._base import BaseInterface

        return BaseInterface(backend, **kwargs)
