import asyncio
import logging

from bbot_server.db.base import BaseDB

from pymongo import AsyncMongoClient
from gridfs import AsyncGridFSBucket

log = logging.getLogger(__name__)


class BaseMongoStore(BaseDB):
    async def setup(self):
        self.client = AsyncMongoClient(self.uri)
        self.db = self.client.get_default_database()
        self.collection_prefix = getattr(self.db_config, "collection_prefix", "")
        bucket_name = f"{self.collection_prefix}fs" if self.collection_prefix else "fs"
        self.fs = AsyncGridFSBucket(self.db, bucket_name=bucket_name)
        # verify connectivity with retry (MongoDB may still be starting)
        while True:
            try:
                await self.client.admin.command("ping")
                break
            except Exception as e:
                log.error(f"Failed to connect to MongoDB at {self.uri}: {e}, retrying...")
                await asyncio.sleep(1)

    async def cleanup(self):
        await self.client.close()


class AssetStore(BaseMongoStore):
    config_key = "asset_store"


class UserStore(BaseMongoStore):
    config_key = "user_store"


class EventStore(BaseMongoStore):
    config_key = "event_store"
