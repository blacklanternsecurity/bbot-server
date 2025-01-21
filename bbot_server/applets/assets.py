from bbot_server.asset_store.asset import Asset
from bbot_server.applets._base import BaseApplet, api_endpoint


class Assets(BaseApplet):
    description = "hostnames and IP addresses discovered during scans"
    include_apps = ["Open_Ports", "DNS_Links", "Emails", "Export"]
    fieldnames = ["host"]

    _data_model = Asset

    @api_endpoint("/detail/{host}", methods=["GET"], summary="Get a single asset by its host")
    async def get_asset(self, host: str) -> Asset:
        asset = await self.collection.find_one({"host": host})
        if not asset:
            self.raise404("Asset not found")
        return Asset(**asset)

    @api_endpoint("/", methods=["GET"], summary="Get assets")
    async def get_assets(self) -> list[Asset]:
        cursor = self.collection.find()
        assets = await cursor.to_list(length=None)
        assets = [Asset(**asset) for asset in assets]
        return assets

    @api_endpoint("/fieldnames", methods=["GET"], summary="List all current asset fieldnames")
    async def get_asset_fieldnames(self) -> list[str]:
        fieldnames = self.all_fieldnames
        return fieldnames
