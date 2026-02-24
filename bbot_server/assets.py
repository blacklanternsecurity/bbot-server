from bbot_server.models.base import BaseAssetFacet


class Asset(BaseAssetFacet):
    """
    The core Asset model.

    Previously, CustomAssetFields subclasses from various modules were merged into this model
    at import time via AST parsing and combine_pydantic_models(). That system has been removed.
    Each module now has its own standalone table.
    """
    __table_name__ = "assets"
    __store_type__ = "asset"
