from pymongo import WriteConcern
from motor.motor_asyncio import AsyncIOMotorClient

from bbot_server.event_store._base import BaseEventStore


class MongoEventStore(BaseEventStore):
    """
    docker run --rm -p 27017:27017 mongo
    """

    async def _setup(self):
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client[self.db_name]
        self.collection = self.db[self.table_name]
        self.strict_collection = self.collection.with_options(write_concern=WriteConcern(w=1, j=True))

    async def _archive_events(self, older_than):
        # we use strict_collection to make sure all the writes complete before we return
        await self.strict_collection.update_many(
            {"timestamp": {"$lt": older_than}, "archived": {"$ne": True}},
            {"$set": {"archived": True}},
        )

    async def _insert_event(self, event):
        event_json = event.model_dump()
        await self.collection.insert_one(event_json)

    async def _get_events(self, host: str, type: str, min_timestamp: float, archived: bool):
        """
        Get all events from the database, or if min_timestamp is provided, get the newest events up to that timestamp
        """
        query = {}
        if type is not None:
            query["type"] = {"$eq": type}
        if min_timestamp is not None:
            query["timestamp"] = {"$gte": min_timestamp}
        if archived is not None:
            query["archived"] = {"$eq": archived}
        if host is not None:
            query["host"] = host
        async for event in self.collection.find(query):
            yield event

    async def _clear(self, confirm):
        if not confirm == f"WIPE {self.db_name}":
            raise ValueError("Confirmation failed")
        await self.collection.delete_many({})

    async def cleanup(self):
        self.client.close()
        await super().cleanup()
