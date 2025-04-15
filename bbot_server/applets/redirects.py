from bbot_server.applets._base import BaseApplet, api_endpoint


class RedirectsApplet(BaseApplet):
    name = "Redirects"
    watched_events = ["URL"]
    description = "HTTP redirects discovered during scans"

    @api_endpoint("/{host}/redirects", methods=["GET"], summary="Get all the redirects for a host")
    async def get_redirects(self, host: str) -> list[str]:
        return []
