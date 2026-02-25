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
        self.engine = None

    async def setup(self):
        # don't try to set up database/message queues if we're connected to a remote instance
        # e.g. through the HTTP interface
        if self.is_native:
            # set up PostgreSQL engine and session factory
            if self._session_factory is None:
                from bbot_server.db.postgres import create_db

                self.engine, self._session_factory = await create_db()

            # set up message queue
            from bbot_server.message_queue import MessageQueue

            self.message_queue = MessageQueue()
            await self.message_queue.setup()

        await self._setup()

        return True, ""

    @property
    def config(self):
        return self._config

    @property
    def _config(self):
        return bbcfg

    async def cleanup(self):
        if self.is_native:
            if self.engine is not None:
                await self.engine.dispose()
            if self.message_queue is not None:
                await self.message_queue.cleanup()
        await self._cleanup()
