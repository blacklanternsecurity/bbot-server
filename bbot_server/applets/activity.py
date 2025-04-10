from bbot_server.models.assets import Activity
from bbot_server.applets._base import BaseApplet, api_endpoint


class ActivityApplet(BaseApplet):
    name = "Activity"
    watched_activities = ["*"]
    description = "Query BBOT server activities"
    route_prefix = ""
    model = Activity

    async def handle_activity(self, activity: Activity):
        # write the activity to the database
        await self.collection.insert_one(activity.model_dump())

    @api_endpoint("/", methods=["GET"], summary="Get all activities")
    async def get_activities(self) -> list[Activity]:
        return await self.collection.find_all()
