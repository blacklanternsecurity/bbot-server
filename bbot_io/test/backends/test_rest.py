from .base import IOTestBase


class TestREST(IOTestBase):
    needs_server = True
    backend = "rest"
    kwargs = dict(url="http://127.0.0.1:7777")
