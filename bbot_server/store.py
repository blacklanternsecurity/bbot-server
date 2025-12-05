from bbot_server.db.base import BaseDB

from pymongo import AsyncMongoClient
from gridfs import AsyncGridFSBucket


class BaseMongoStore(BaseDB):
    async def setup(self):
        self.client = AsyncMongoClient(self.uri)
        self.db = self.client.get_database(self.db_name)
        self.fs = AsyncGridFSBucket(self.db)

    async def cleanup(self):
        await self.client.close()


class AssetStore(BaseMongoStore):
    config_key = "asset_store"


class UserStore(BaseMongoStore):
    config_key = "user_store"


class EventStore(BaseMongoStore):
    config_key = "event_store"
