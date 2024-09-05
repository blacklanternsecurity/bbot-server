from .base import IOTestBase


class TestSqlite(IOTestBase):
    async def setup(self):
        from bbot_io import BBOT_IO

        return BBOT_IO(database="/tmp/bbot-io-test.db")
