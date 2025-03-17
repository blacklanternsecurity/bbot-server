from pathlib import Path
from contextlib import suppress
from gridfs import GridFSBucket
from omegaconf import OmegaConf

from bbot_server.applets._base import BaseApplet
from bbot_server.config import BBOT_SERVER_CONFIG
from bbot_server.utils.misc import combine_pydantic_models

# assets imports
from bbot_server.applets.assets import AssetsApplet
from bbot_server.applets.events import EventsApplet
from bbot_server.applets.scans.scans import ScansApplet


class RootApplet(BaseApplet):
    include_apps = [AssetsApplet, EventsApplet, ScansApplet]

    name = "Root Applet"

    nested = False

    _route_prefix = ""

    def __init__(self, config=None, **kwargs):
        """
        "config" can be either a path to a config file or an OmegaConf object
        """
        if config is not None:
            with suppress(Exception):
                config_path = Path(config)
                config = OmegaConf.load(config_path)
            self.config = OmegaConf.merge(BBOT_SERVER_CONFIG, config)
        else:
            self.config = BBOT_SERVER_CONFIG
        super().__init__(**kwargs)

    async def setup(self):
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

        # from bbot_server.models.assets import Asset

        # # the combined model containing all the custom asset fields defined by applets
        # combined_model = combine_pydantic_models(self.all_asset_models, model_name="AssetModel")
        # # ensure every field has a type validator and default factory
        # for field, field_info in combined_model.model_fields.items():
        #     if field_info.annotation is None:
        #         raise ValueError(f"Field '{field}' has no type annotation")
        #     if field_info.default_factory is None:
        #         raise ValueError(f"Field '{field}' has no default factory")

        # Asset._field_validator = combined_model

    async def cleanup(self):
        for child_applet in self.child_applets:
            await child_applet.cleanup()
        await self.asset_store.cleanup()
        await self.event_store.cleanup()
        await self.message_queue.cleanup()
