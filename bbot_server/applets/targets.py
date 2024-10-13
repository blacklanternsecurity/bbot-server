from bbot_server.models import Target
from bbot_server.applets._base import BaseApplet, api_endpoint


class Targets(BaseApplet):

    description = "manage the current target - whitelists, blacklists, etc."
    data_model = Target

    @api_endpoint("/", methods=["GET"], summary="Get Targets")
    async def get_targets(self) -> list[Target]:
        return await self.db.find_many()

    @api_endpoint("/", methods=["PUT"], summary="Create Target")
    async def create_target(self, target: Target):
        target_count = await self.db.count()
        # if this is the first target, make it the default
        target.is_default = target_count == 0
        return await self.db.insert_if_not_exists(target)

    @api_endpoint("/count", methods=["GET"], summary="Count Targets")
    async def count(self):
        return await self.db.count()
