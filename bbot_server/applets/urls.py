from bbot_server.applets._base import BaseApplet, api_endpoint


class URLsApplet(BaseApplet):
    name = "URLs"
    description = "URLs discovered during BBOT scans"

    @api_endpoint("/", methods=["GET"], summary="Get all URLs")
    async def get_urls(self) -> list[str]:
        return []
