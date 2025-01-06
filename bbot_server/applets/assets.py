from bbot_server.asset_store.asset import Asset
from bbot_server.applets._base import BaseApplet, api_endpoint


class Assets(BaseApplet):
    include_apps = ["Open_Ports", "DNS_Links", "Emails"]

    description = "hostnames and IP addresses discovered during scans"
    _data_model = Asset

    @api_endpoint("/{host}", methods=["GET"], summary="Get a single asset by its host")
    async def get_asset(self, host: str) -> Asset:
        print("GETTING ASSET", host)

    @api_endpoint("/", methods=["GET"], summary="Get assets")
    async def get_assets(self) -> list[Asset]:
        cursor = self.collection.find()
        assets = await cursor.to_list(length=None)
        assets = [Asset(**asset) for asset in assets]
        return assets
