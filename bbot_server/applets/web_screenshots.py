from bbot.models.pydantic import Event
from bbot_server.models.activity_models import Activity
from bbot_server.applets._base import BaseApplet, api_endpoint


class WebScreenshotsApplet(BaseApplet):
    name = "Web Screenshots"
    watched_events = ["WEBSCREENSHOT"]
    description = "web screenshots taken during scans"
    route_prefix = ""

    async def handle_event(self, event: Event, asset) -> list[Activity]:
        return []

    @api_endpoint("/webscreenshots", methods=["GET"], summary="Get all web screenshots")
    async def get_webscreenshots(self) -> list[str]:
        return []

    @api_endpoint("/{host}/webscreenshots", methods=["GET"], summary="Get web screenshots by hostname")
    async def get_webscreenshots_by_host(self, domain: str) -> list[str]:
        return []
