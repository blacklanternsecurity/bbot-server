from contextlib import suppress

from bbot_server.models.activity_models import Activity
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

    @api_endpoint("/", methods=["GET"], type="http_stream", response_model=Activity, summary="Stream all activities")
    async def get_activities(self, host: str = None, type: str = None):
        query = {}
        if host:
            query["host"] = host
        if type:
            query["type"] = type
        async for activity in self.collection.find(query):
            yield self.model(**activity)

    @api_endpoint("/tail", type="websocket_stream_outgoing", response_model=Activity)
    async def tail_activities(self, n: int = 0):
        agen = self.message_queue.tail_activities(n=n)
        try:
            async for activity in agen:
                yield activity
        finally:
            with suppress(BaseException):
                await agen.aclose()
