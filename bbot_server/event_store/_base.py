from omegaconf import OmegaConf

from bbot.models.pydantic import Event
from bbot_server.config import BBOT_SERVER_CONFIG


class BaseEventStore:
    def __init__(self, config=None):
        self.global_config = BBOT_SERVER_CONFIG
        try:
            self.config = self.global_config.event_store
            if config is not None:
                self.config = OmegaConf.merge(self.config, config)
        except Exception as e:
            raise ValueError("Event store configuration is missing") from e
        try:
            self.uri = self.config.uri
        except Exception as e:
            raise ValueError("Event store URI is missing") from e

    @property
    def db_name(self):
        if self.config.uri.count("/") == 3:
            db_name = self.config.uri.split("/")[-1]
            if not db_name:
                raise ValueError("Database name must be included in the URI.")
            return db_name
        raise ValueError(f"Invalid URI: {self.config.uri} - Database name must be included.")

    async def setup(self):
        await self._setup()

    async def insert_event(self, event):
        if not isinstance(event, Event):
            raise ValueError("Event must be an instance of Event")
        await self._insert_event(event)

    async def get_events(self):
        async for event in self._get_events():
            yield Event(**event)

    async def clear(self, confirm):
        await self._clear(confirm)

    async def _setup(self):
        raise NotImplementedError()

    async def _insert_event(self, event):
        raise NotImplementedError()

    async def _get_events(self):
        raise NotImplementedError()

    async def _clear(self, confirm):
        raise NotImplementedError()
