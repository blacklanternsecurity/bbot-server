from .base import IOTestBase


class TestSqlite(IOTestBase):
    backend = "sqlite"
    kwargs = dict(database="/tmp/bbot-io-test.db")
