from . import IOTestBase


class TestHTTP(IOTestBase):
    needs_server = True
    backend = "http"
    kwargs = dict(url="http://127.0.0.1:7777")
