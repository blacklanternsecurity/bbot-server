from pymongo import WriteConcern
from motor.motor_asyncio import AsyncIOMotorClient


from bbot_server.errors import BBOTServerNotFoundError
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
        result = await self.strict_collection.update_many(
            {"timestamp": {"$lt": older_than}, "archived": {"$ne": True}},
            {"$set": {"archived": True}},
        )
        self.log.info(f"Archived {result.modified_count} events")

    async def _insert_event(self, event):
        event_json = event.model_dump()
        await self.collection.insert_one(event_json)

    async def _get_events(self, host: str, type: str, min_timestamp: float, archived: bool, active: bool):
        """
        Get all events from the database, or if min_timestamp is provided, get the newest events up to that timestamp
        """
        query = {}
        if type is not None:
            query["type"] = {"$eq": type}
        if min_timestamp is not None:
            query["timestamp"] = {"$gte": min_timestamp}
        if not (active and archived):
            if not (active or archived):
                raise ValueError("Must query at least one of active or archived")
            query["archived"] = {"$eq": archived}
        if host is not None:
            query["host"] = host
        async for event in self.collection.find(query):
            yield event

    async def _get_event(self, uuid: str):
        event = await self.collection.find_one({"uuid": uuid})
        if event is None:
            raise BBOTServerNotFoundError(f"Event {uuid} not found")
        return event

    async def _clear(self, confirm):
        if not confirm == f"WIPE {self.db_name}":
            raise ValueError("Confirmation failed")
        await self.collection.delete_many({})

    async def cleanup(self):
        self.client.close()
        await super().cleanup()
