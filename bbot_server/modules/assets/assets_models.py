from bbot_server.models.base import AssetQuery


class AssetOnlyQuery(AssetQuery):
    """Query for host assets only."""
    pass


class AdvancedAssetQuery(AssetQuery):
    """Advanced asset query with all AssetQuery features."""
    pass
