import orjson

from bbot.models.pydantic import Event
from bbot_server.db.base import BaseDB
from bbot_server.message_queue import MessageQueue


INGESTOR_PROCESS = None


class BaseEventStore(BaseDB):
    config_key = "event_store"

    async def insert_event(self, event):
        if not isinstance(event, Event):
            raise ValueError("Event must be an instance of Event")
        await self._insert_event(event)

    async def setup(self):
        message_queue = MessageQueue()
        await message_queue.setup()

        async def event_callback(message):
            try:
                message_json = orjson.loads(message.body)
                await self.insert_event(Event(**message_json))
            except Exception as e:
                print(f"Error inserting event: {e}")

        await message_queue.subscribe(event_callback, "bbot.events")
        await super().setup()

    async def get_events(self):
        return [Event(**event) for event in await self._get_events()]

    async def clear(self, confirm):
        await self._clear(confirm)

    async def _insert_event(self, event):
        raise NotImplementedError()

    async def _get_events(self):
        raise NotImplementedError()

    async def _clear(self, confirm):
        raise NotImplementedError()
