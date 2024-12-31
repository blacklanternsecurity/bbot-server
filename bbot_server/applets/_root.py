from bbot_server.applets._base import BaseApplet, api_endpoint


class RootApplet(BaseApplet):
    include_apps = ["Assets", "Events"]

    nested = False

    _route_prefix = ""

    async def setup(self):
        # set up asset store
        if self.asset_store is None:
            from bbot_server.asset_store import MongoAssetStore

            self.asset_store = MongoAssetStore()
            await self.asset_store.setup()

        # set up event store
        from bbot_server.event_store import EventStore

        self.event_store = EventStore()
        await self.event_store.setup()

        # set up NATS client
        from bbot_server.message_queue import MessageQueue

        self.message_queue = MessageQueue()
        await self.message_queue.setup()

    @api_endpoint("/", methods=["GET"], summary="Get the root endpoint")
    async def get_root(self):
        return {"message": "Hello, World!"}

    async def cleanup(self):
        await self.message_queue.cleanup()
