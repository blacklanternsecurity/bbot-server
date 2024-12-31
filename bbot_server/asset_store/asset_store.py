from bbot_server.db.base import BaseDB


class BaseAssetStore(BaseDB):
    config_key = "asset_store"


from motor.motor_asyncio import AsyncIOMotorClient


class MongoAssetStore(BaseAssetStore):
    async def setup(self):
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client.get_database(self.db_name)
