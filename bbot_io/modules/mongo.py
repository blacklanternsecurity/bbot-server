from pymongo import ASCENDING
from motor.motor_asyncio import AsyncIOMotorClient

from bbot_io.models import *
from bbot_io.modules.base import BaseIO


class mongo(BaseIO):

    def setup(self, uri: str = "mongodb://localhost:27017", db_name: str = "bbot", collection_name: str = "events"):
        self.uri = uri
        self.db_name = db_name
        self.collection_name = collection_name
        self.client = AsyncIOMotorClient(self.uri)
        self.database = getattr(self.client, db_name)
        self.collection = getattr(self.database, collection_name)

        for field in ("id", "type", "host", "timestamp", "module", "scan"):
            self.collection.create_index([(field, ASCENDING)])

    async def insert_event(self, event: Event):
        event_dict = event.model_dump(exclude_none=True)
        await self.collection.insert_one(event_dict)

    async def get_scans(self, limit: int = None):
        return await self.collection.find({"type": {"$eq": "SCAN"}}).to_list(limit)

    async def get_subdomains(
        self,
    ):
        return await self.collection.distinct("host", {"type": {"$eq": "DNS_NAME"}})

    async def get_events(self, limit: int = None):
        return [Event(**e) for e in await self.collection.find().to_list(None)]

    async def drop_database(self):
        return await self.database.drop_collection(self.collection_name)
