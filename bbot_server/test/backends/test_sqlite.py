from .base import IOTestBase


class TestSqlite(IOTestBase):
    backend = "sqlite"
    kwargs = dict(database="/tmp/.bbotio_test/test.db")
