import traceback
from bbot.models.pydantic import Event
from bbot_server.db.base import BaseDB
from bbot_server.message_queue import MessageQueue


class BaseEventStore(BaseDB):
    config_key = "event_store"

    async def insert_event(self, event):
        if not isinstance(event, Event):
            raise ValueError("Event must be an instance of Event")
        await self._insert_event(event)

    async def archive_event(self, uuid):
        await self._archive_event(uuid)

    async def get_events(self):
        return [Event(**event) for event in await self._get_events()]

    async def clear(self, confirm):
        await self._clear(confirm)

    async def _insert_event(self, event):
        raise NotImplementedError()

    async def _archive_event(self, uuid):
        raise NotImplementedError()

    async def _get_events(self):
        raise NotImplementedError()

    async def _clear(self, confirm):
        raise NotImplementedError()

    async def cleanup(self):
        pass
