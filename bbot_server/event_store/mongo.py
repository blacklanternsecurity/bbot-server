from motor.motor_asyncio import AsyncIOMotorClient

from bbot_server.event_store._base import BaseEventStore


class mongo(BaseEventStore):
    async def _setup(self):
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client[self.db_name]
        self.collection = self.db.events

    async def _insert_event(self, event):
        event_json = event.model_dump()
        await self.collection.insert_one(event_json)

    async def _get_events(self, min_timestamp=None):
        """
        Get all events from the database, or if min_timestamp is provided, get the newest events up to that timestamp
        """
        query = {}
        if min_timestamp:
            query["timestamp"] = {"$gte": min_timestamp}
        cursor = self.collection.find(query)

        async for event in cursor:
            yield event

    async def _clear(self, confirm):
        if not confirm == f"WIPE {self.db_name}":
            raise ValueError("Confirmation failed")
        await self.collection.delete_many({})
