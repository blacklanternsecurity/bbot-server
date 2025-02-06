from bbot.models.pydantic import Event
from bbot_server.models.assets import Asset, AssetActivity
from bbot_server.applets._base import BaseApplet, api_endpoint


class WebScreenshotsApplet(BaseApplet):
    watched_events = ["WEBSCREENSHOT"]
    description = "web screenshots taken during scans"
    route_prefix = ""

    async def ingest_event(self, asset: Asset, event: Event) -> list[AssetActivity]:
        return []

    @api_endpoint("/webscreenshots", methods=["GET"], summary="Get all web screenshots")
    async def get_webscreenshots(self) -> list[str]:
        return []

    @api_endpoint("/{host}/webscreenshots", methods=["GET"], summary="Get web screenshots by hostname")
    async def get_webscreenshots_by_host(self, domain: str) -> list[str]:
        return []
