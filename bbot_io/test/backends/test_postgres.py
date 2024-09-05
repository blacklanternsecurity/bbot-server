from .base import IOTestBase


class TestPostgres(IOTestBase):
    async def setup(self):
        from bbot_io import BBOT_IO

        return BBOT_IO("postgres", password="bbotislife")
