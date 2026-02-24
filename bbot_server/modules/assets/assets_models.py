from pydantic import Field

from bbot_server.models.base import AssetQuery


class AssetOnlyQuery(AssetQuery):
    _force_asset_type = "Asset"


class AdvancedAssetQuery(AssetQuery):
    """Allow the user to specify what type of asset they want"""

    type: str = Field(default="Asset", description="Asset type (Asset, Finding, Technology, etc.)")

    async def build(self, applet=None):
        stmt = await super().build(applet)
        model = self._applet.model

        if self.type:
            stmt = stmt.where(model.type == self.type)

        return stmt
