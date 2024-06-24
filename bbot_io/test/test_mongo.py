from .lib import *


class TestMongo(IOTestBase):
    async def setup(self):
        from bbot_io.modules.mongo import mongo

        return mongo(db_name="bbot_pytest", collection_name="events_pytest")
