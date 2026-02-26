from bbot_server.db.base import BaseDB

from pymongo import AsyncMongoClient
from gridfs import AsyncGridFSBucket


class BaseMongoStore(BaseDB):
    async def setup(self):
        self.client = AsyncMongoClient(self.uri)
        self.db = self.client.get_database(self.db_name)
        self.collection_prefix = getattr(self.db_config, "collection_prefix", "")
        bucket_name = f"{self.collection_prefix}fs" if self.collection_prefix else "fs"
        self.fs = AsyncGridFSBucket(self.db, bucket_name=bucket_name)

    async def cleanup(self):
        await self.client.close()


class AssetStore(BaseMongoStore):
    config_key = "asset_store"


class UserStore(BaseMongoStore):
    config_key = "user_store"


class EventStore(BaseMongoStore):
    config_key = "event_store"
