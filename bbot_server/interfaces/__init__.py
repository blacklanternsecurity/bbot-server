def BBOTInterface(backend="sqlite", **kwargs):
    backend = backend.strip().lower()
    if backend == "http":
        from bbot_server.interfaces.http import HTTPInterface

        # we don't actually use sqlite here, it's used only as a placeholder
        return HTTPInterface("sqlite", **kwargs)

    else:
        from bbot_server.interfaces._base import BaseInterface

        return BaseInterface(backend, **kwargs)
