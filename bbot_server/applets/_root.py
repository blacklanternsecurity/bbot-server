from omegaconf import OmegaConf

from bbot_server.applets._base import BaseApplet
from bbot_server.config import BBOT_SERVER_CONFIG

# assets imports
from bbot_server.applets.assets import AssetsApplet
from bbot_server.applets.events import EventsApplet
from bbot_server.applets.scans.scans import ScansApplet
from bbot_server.applets.targets import TargetsApplet
from bbot_server.applets.activity import ActivityApplet


class RootApplet(BaseApplet):
    include_apps = [AssetsApplet, EventsApplet, ScansApplet, TargetsApplet, ActivityApplet]

    name = "Root Applet"

    _nested = False

    _route_prefix = ""

    def __init__(self, config=None, **kwargs):
        """
        "config" can be either a dictionary or an omegaconf object
        """
        super().__init__(**kwargs)
        if config is not None:
            self._config = OmegaConf.merge(BBOT_SERVER_CONFIG, config)
        else:
            self._config = BBOT_SERVER_CONFIG
        self._interface_type = "python"

    async def setup(self):
        # don't try to set up database/message queues if we're connected to a remote instance
        # e.g. through the HTTP interface
        if self.is_native:
            # set up asset store, user store, and gridfs buckets
            if self.asset_store is None:
                from bbot_server.store.user_store import UserStore
                from bbot_server.store.asset_store import AssetStore

                self.asset_store = AssetStore(self.config)
                await self.asset_store.setup()
                self.asset_db = self.asset_store.db
                self.asset_fs = self.asset_store.fs

                self.user_store = UserStore(self.config)
                await self.user_store.setup()
                self.user_db = self.user_store.db
                self.user_fs = self.user_store.fs

            # set up event store
            from bbot_server.event_store import EventStore

            self.event_store = EventStore(self.config)
            await self.event_store.setup()

            # set up NATS client
            from bbot_server.message_queue import MessageQueue

            self.message_queue = MessageQueue(self.config)
            await self.message_queue.setup()

        await self._setup()

    async def cleanup(self):
        if self.is_native:
            await self.asset_store.cleanup()
            await self.user_store.cleanup()
            await self.event_store.cleanup()
            await self.message_queue.cleanup()
        await self._cleanup()
