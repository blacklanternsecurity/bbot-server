from bbot_server.applets._base import BaseApplet, api_endpoint


class Utils(BaseApplet):

    @api_endpoint("/drop_database", methods=["GET"])
    async def drop_database(self):
        return await self.backend.drop_database()
