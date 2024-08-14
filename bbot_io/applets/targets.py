from bbot_io.models import Target
from bbot_io.applets.base import BaseApplet, api_endpoint


class Targets(BaseApplet):

    model = Target

    @api_endpoint("/", methods=["GET"], summary="Get Targets")
    async def get_targets(self, event_id: str) -> list[Target]:
        return await self.db.find()

    @api_endpoint("/", methods=["PUT"], summary="Create Target")
    async def put_target(self, target: Target):
        # target_count = await self.db.count()
        return await self.db.insert(target)

    @api_endpoint("/count", methods=["GET"], summary="Count Targets")
    async def count(self):
        return await self.db.count()
