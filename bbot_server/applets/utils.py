from bbot_server.applets._base import BaseApplet, api_endpoint


class Utils(BaseApplet):

    model = None

    @api_endpoint("/drop_database", methods=["GET"])
    async def drop_database(self):
        return await self.backend.drop_database()
