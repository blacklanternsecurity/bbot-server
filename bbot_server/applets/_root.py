from bbot_server.applets._base import BaseApplet


class RootApplet(BaseApplet):
    include_apps = ["Assets", "Events", "Scans", "Agents"]

    nested = False

    _route_prefix = ""

    async def setup(self):
        # set up asset store
        if self.asset_store is None:
            from bbot_server.asset_store import MongoAssetStore

            self.asset_store = MongoAssetStore()
            await self.asset_store.setup()
        else:
            print(f"ASSET STORE ALREADY SET UP: {self.asset_store}")

        # set up event store
        from bbot_server.event_store import EventStore

        self.event_store = EventStore()
        await self.event_store.setup()

        # set up NATS client
        from bbot_server.message_queue import MessageQueue

        self.message_queue = MessageQueue()
        await self.message_queue.setup()

        await self._setup()

    async def cleanup(self):
        for child_applet in self.child_applets:
            await child_applet.cleanup()
        await self.asset_store.cleanup()
        await self.event_store.cleanup()
        await self.message_queue.cleanup()
