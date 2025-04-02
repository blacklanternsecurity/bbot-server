from .base_store import BaseMongoStore


class AssetStore(BaseMongoStore):
    config_key = "asset_store"
