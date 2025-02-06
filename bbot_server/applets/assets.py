from contextlib import suppress

# applets imports
from bbot_server.applets.findings import FindingsApplet
from bbot_server.applets.open_ports import OpenPortsApplet
from bbot_server.applets.dns_links import DNSLinksApplet
from bbot_server.applets.emails import EmailsApplet
from bbot_server.applets.web_screenshots import WebScreenshotsApplet
from bbot_server.applets.export import ExportApplet

# watchdog
# from bbot_server.watchdogs.assets import AssetsWatchdog

# pydantic
from bbot.models.pydantic import Event
from bbot_server.models.assets import AssetActivity, BaseAssetFacet

from bbot_server.applets._base import BaseApplet, api_endpoint


class Asset(BaseAssetFacet):
    __tablename__ = "assets"


class AssetsApplet(BaseApplet):
    name = "Assets"
    description = "hostnames and IP addresses discovered during scans"
    include_apps = [FindingsApplet, OpenPortsApplet, DNSLinksApplet, EmailsApplet, WebScreenshotsApplet, ExportApplet]
    # watchdogs = [AssetsWatchdog]
    model = Asset

    @api_endpoint("/", methods=["GET"], summary="Get assets")
    async def get_assets(self) -> list[Asset]:
        # cursor = self.collection.find()
        # assets = await cursor.to_list(length=None)
        # assets = [Asset(**asset) for asset in assets]
        # return assets
        return []

    @api_endpoint("/{host}/list", methods=["GET"], summary="List assets by host (including subdomains)")
    async def get_assets_by_host(self, host: str) -> list[Asset]:
        cursor = self.collection.find({"reverse_host": {"$regex": f"^{host[::-1]}."}})
        assets = await cursor.to_list(length=None)
        assets = [Asset(**asset) for asset in assets]
        return assets

    @api_endpoint("/{host}/detail", methods=["GET"], summary="Get a single asset by its host")
    async def get_asset(self, host: str) -> Asset:
        asset = await self.collection.find_one({"host": host})
        if not asset:
            self.raise404("Asset not found")
        return Asset(**asset)

    @api_endpoint("/fieldnames", methods=["GET"], summary="List all current asset fieldnames")
    async def get_asset_fieldnames(self) -> list[str]:
        fieldnames = self.all_fieldnames
        return fieldnames

    @api_endpoint("/tail", type="websocket", response_model=AssetActivity)
    async def tail_assets(self):
        agen = self.message_queue.asset_tail()
        try:
            async for activity in agen:
                yield activity
        finally:
            with suppress(BaseException):
                await agen.aclose()

    async def update_asset(self, asset: Asset):
        await self.strict_collection.update_one({"host": asset.host}, {"$set": asset.model_dump()})
