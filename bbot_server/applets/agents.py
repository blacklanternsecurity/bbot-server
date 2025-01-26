from bbot_server.applets._base import BaseApplet, api_endpoint


class Agents(BaseApplet):
    watched_events = []
    description = "Manage BBOT scan agents"

    @api_endpoint("/", methods=["GET"], summary="Get all agents")
    async def get_agents(self) -> list[str]:
        print("GETTING AGENTS")
        return []
