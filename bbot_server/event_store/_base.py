from bbot.models.pydantic import Event
from bbot_server.db.base import BaseDB


class BaseEventStore(BaseDB):
    config_key = "event_store"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event_store_config = self.config.get("event_store", {})
        self.archive_after_days = self.event_store_config.get("archive_after", 90)
        self.archive_cron = self.event_store_config.get("archive_cron", "0 0 * * *")

    async def insert_event(self, event):
        if not isinstance(event, Event):
            raise ValueError("Event must be an instance of Event")
        await self._insert_event(event)

    async def get_event(self, uuid: str):
        event = await self._get_event(uuid)
        return Event(**event)

    async def get_events(self, host: str = None, type=None, min_timestamp=None, archived=False, active=True):
        async for event in self._get_events(
            host=host, type=type, min_timestamp=min_timestamp, archived=archived, active=active
        ):
            yield Event(**event)

    async def archive_events(self, older_than=None):
        if older_than is None:
            older_than = self.archive_after_timestamp
        return await self._archive_events(older_than)

    async def clear(self, confirm):
        await self._clear(confirm)

    async def _insert_event(self, event):
        raise NotImplementedError()

    async def _archive_events(self, uuid):
        raise NotImplementedError()

    async def _get_events(self):
        raise NotImplementedError()

    async def _clear(self, confirm):
        raise NotImplementedError()

    async def cleanup(self):
        pass
