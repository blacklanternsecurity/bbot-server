from pymongo import WriteConcern, AsyncMongoClient


from bbot_server.errors import BBOTServerNotFoundError, BBOTServerValueError
from bbot_server.event_store._base import BaseEventStore


class MongoEventStore(BaseEventStore):
    """
    docker run --rm -p 127.0.0.1:27017:27017 mongo
    """

    async def _setup(self):
        self.client = AsyncMongoClient(self.uri)
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

    async def _get_events(
        self,
        host: str,
        domain: str,
        type: str,
        scan: str,
        min_timestamp: float,
        max_timestamp: float,
        active: bool,
        archived: bool,
    ):
        """
        Get all events from the database based on the provided filters
        """
        query = {}
        if type is not None:
            query["type"] = type
        if min_timestamp is not None:
            query["timestamp"] = {"$gte": min_timestamp}
        # if both active and archived are true, we don't need to filter anything
        if not (active and archived):
            # if both are false, we need to raise an error
            if not (active or archived):
                raise BBOTServerValueError("Must query at least one of active or archived")
            # otherwise if only one is true, we need to filter by the other
            query["archived"] = {"$eq": archived}
        if max_timestamp is not None:
            query["timestamp"] = {"$lte": max_timestamp}
        if scan is not None:
            query["scan"] = scan
        if host is not None:
            query["host"] = host
        if domain is not None:
            # match reverse_host with regex
            reversed_host = domain[::-1]
            query["reverse_host"] = {"$regex": f"^{reversed_host}(\\.|$)"}
        self.log.debug(f"Querying events: {query}")
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
        await self.client.close()
        await super().cleanup()
