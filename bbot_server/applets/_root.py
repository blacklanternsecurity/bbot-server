from bbot_server.config import BBOT_SERVER_CONFIG as bbcfg
from bbot_server.applets.base import BaseApplet


class RootApplet(BaseApplet):
    name = "Root Applet"

    _nested = False

    _route_prefix = ""

    def __init__(self, config=None, **kwargs):
        """
        "config" can be a dictionary of config overrides
        """
        if config is not None:
            bbcfg.refresh(**config)
        super().__init__(**kwargs)
        self._interface_type = "python"
        self._mcp = None

    async def setup(self):
        # don't try to set up database/message queues if we're connected to a remote instance
        # e.g. through the HTTP interface
        if self.is_native:
            # set up asset store, user store, and gridfs buckets
            if self.asset_store is None:
                from bbot_server.store import UserStore, AssetStore, EventStore

                self.asset_store = AssetStore()
                await self.asset_store.setup()

                self.user_store = UserStore()
                await self.user_store.setup()

                self.event_store = EventStore()
                await self.event_store.setup()

            # set up message queue
            from bbot_server.message_queue import MessageQueue

            self.message_queue = MessageQueue()
            await self.message_queue.setup()

        await self._setup()

        # Reconcile indexes after all applets are set up
        if self.is_native and bbcfg.reconcile_indexes:
            await self.reconcile_all_indexes()

        return True, ""

    @property
    def config(self):
        return self._config

    @property
    def _config(self):
        return bbcfg

    async def cleanup(self):
        if self.is_native:
            await self.asset_store.cleanup()
            await self.user_store.cleanup()
            await self.event_store.cleanup()
            await self.message_queue.cleanup()
        await self._cleanup()
