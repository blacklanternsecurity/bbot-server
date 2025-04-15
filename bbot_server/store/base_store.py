from bbot_server.db.base import BaseDB


from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket


class BaseMongoStore(BaseDB):
    async def setup(self):
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client.get_database(self.db_name)
        self.fs = AsyncIOMotorGridFSBucket(self.db)

    async def cleanup(self):
        self.client.close()
