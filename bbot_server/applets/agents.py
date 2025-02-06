from bbot_server.applets._base import BaseApplet, api_endpoint


class AgentsApplet(BaseApplet):
    name = "Agents"
    description = "manage BBOT scan agents"

    @api_endpoint("/", methods=["GET"], summary="Get all agents")
    async def get_agents(self) -> list[str]:
        return []
