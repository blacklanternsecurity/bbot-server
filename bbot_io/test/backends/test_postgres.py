from .base import IOTestBase


class TestPostgres(IOTestBase):
    async def setup(self):
        from bbot_io import BBOTIO

        return BBOTIO("postgres", password="bbotislife")
