from .lib import *


class TestSqlite(IOTestBase):
    async def setup(self):
        from bbot_io import BBOTIO

        return BBOTIO(database="/tmp/bbot-io-test.db")
