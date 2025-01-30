from omegaconf import OmegaConf

from bbot_server.applets._base import BaseApplet
from bbot_server.config import BBOT_SERVER_CONFIG
from bbot_server.utils.misc import combine_pydantic_models


class RootApplet(BaseApplet):
    include_apps = ["Assets", "Events", "Scans", "Agents"]

    nested = False

    _route_prefix = ""

    def __init__(self, **kwargs):
        config = kwargs.pop("config", {})
        if config:
            self.config = OmegaConf.merge(BBOT_SERVER_CONFIG, config)
        else:
            self.config = BBOT_SERVER_CONFIG
        super().__init__(**kwargs)

    async def setup(self):
        # set up asset store
        if self.asset_store is None:
            from bbot_server.asset_store import MongoAssetStore

            self.asset_store = MongoAssetStore(self.config)
            await self.asset_store.setup()

        # set up event store
        from bbot_server.event_store import EventStore

        self.event_store = EventStore(self.config)
        await self.event_store.setup()

        # set up NATS client
        from bbot_server.message_queue import MessageQueue

        self.message_queue = MessageQueue(self.config)
        await self.message_queue.setup()

        await self._setup()

        from bbot_server.models.assets import Asset

        # the combined model containing all the custom asset fields defined by applets
        combined_model = combine_pydantic_models(self.all_asset_models, model_name="AssetModel")
        # ensure every field has a type validator and default factory
        for field, field_info in combined_model.model_fields.items():
            if field_info.annotation is None:
                raise ValueError(f"Field '{field}' has no type annotation")
            if field_info.default_factory is None:
                raise ValueError(f"Field '{field}' has no default factory")

        Asset._field_validator = combined_model

    async def cleanup(self):
        for child_applet in self.child_applets:
            await child_applet.cleanup()
        await self.asset_store.cleanup()
        await self.event_store.cleanup()
        await self.message_queue.cleanup()
