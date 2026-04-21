from contextlib import suppress

from bbot_server.assets import Asset
from bbot_server.applets.base import BaseApplet, api_endpoint
from bbot_server.modules.activity.activity_models import Activity, ActivityQuery


class ActivityApplet(BaseApplet):
    name = "Activity"
    watched_activities = ["*"]
    description = "Query BBOT server activities"
    model = Activity

    async def handle_activity(self, activity: Activity, asset: Asset = None):
        # write the activity to the database
        await self.collection.insert_one(activity.model_dump())

    @api_endpoint(
        "/list", methods=["GET"], type="http_stream", response_model=Activity, summary="Stream all activities", mcp=True
    )
    async def list_activities(self, host: str = None, type: str = None):
        query = {}
        if host:
            query["host"] = host
        if type:
            query["type"] = type
        async for activity in self.collection.find(query, sort=[("timestamp", 1), ("created", 1)]):
            yield self.model(**activity)

    @api_endpoint("/query", methods=["POST"], type="http_stream", response_model=dict, summary="List activities", mcp=True)
    async def query_activities(self, query: ActivityQuery):
        """
        Advanced querying of activities. Choose your own filters and fields.
        """
        async for activity in query.mongo_iter(self):
            yield activity

    @api_endpoint("/count", methods=["POST"], summary="Count activities", mcp=True)
    async def count_activities(self, query: ActivityQuery) -> int:
        """
        Same as query_activities, except only returns the count
        """
        return await query.mongo_count(self)

    @api_endpoint("/tail", type="websocket_stream_outgoing", response_model=Activity)
    async def tail_activities(self, n: int = 0):
        agen = self.message_queue.tail_activities(n=n)
        try:
            async for activity in agen:
                yield activity
        finally:
            with suppress(BaseException):
                await agen.aclose()
