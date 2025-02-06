from pymongo import WriteConcern
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

from bbot_server.event_store._base import BaseEventStore


class mongo(BaseEventStore):
    """
    docker run --rm -p 27017:27017 mongo
    """

    async def _setup(self):
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client[self.db_name]
        self.collection = self.db[self.table_name]
        self.strict_collection = self.collection.with_options(write_concern=WriteConcern(w=1, j=True))

    async def archive_events(self):
        archive_after = self.config.get("event_store", {}).get("archive_after", 90)
        min_timestamp = datetime.now(datetime.UTC) - timedelta(days=archive_after)
        # we use strict_collection to ensure all the writes complete before we return
        await self.strict_collection.update_many(
            {"timestamp": {"$lt": min_timestamp}, "archived": {"$ne": True}},
            {"$set": {"archived": True}},
        )

    async def _insert_event(self, event):
        event_json = event.model_dump()
        await self.collection.insert_one(event_json)

    async def _get_events(self, min_timestamp=None, archived=None, host: str = None):
        """
        Get all events from the database, or if min_timestamp is provided, get the newest events up to that timestamp
        """
        query = {}
        if min_timestamp is not None:
            query["timestamp"] = {"$gte": min_timestamp}
        if archived is False:
            query["archived"] = {"$eq": False}
        elif archived is True:
            query["archived"] = {"$eq": True}
        if host is not None:
            query["host"] = host
        return await self.collection.find(query).to_list(None)

    async def _clear(self, confirm):
        if not confirm == f"WIPE {self.db_name}":
            raise ValueError("Confirmation failed")
        await self.collection.delete_many({})

    async def cleanup(self):
        self.client.close()
        await super().cleanup()
