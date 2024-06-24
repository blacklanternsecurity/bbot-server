from .lib import *


class TestSqlite(IOTestBase):
    async def setup(self):
        from bbot_io.modules.sqlite import sqlite

        return sqlite(table_name="events_pytest")
