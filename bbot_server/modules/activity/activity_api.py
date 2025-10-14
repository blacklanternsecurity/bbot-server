from contextlib import suppress

from bbot_server.assets import Asset
from bbot_server.applets.base import BaseApplet, api_endpoint
from bbot_server.modules.activity.activity_models import Activity


class ActivityApplet(BaseApplet):
    name = "Activity"
    watched_activities = ["*"]
    description = "Query BBOT server activities"
    model = Activity

    async def handle_activity(self, activity: Activity, asset: Asset = None):
        # write the activity to the database
        await self.collection.insert_one(activity.model_dump())

    @api_endpoint(
        "/list", methods=["GET"], type="http_stream", response_model=Activity, summary="Stream all activities"
    )
    async def list_activities(self, host: str = None, type: str = None):
        query = {}
        if host:
            query["host"] = host
        if type:
            query["type"] = type
        async for activity in self.collection.find(query, sort=[("timestamp", 1), ("created", 1)]):
            yield self.model(**activity)

    @api_endpoint("/query", methods=["POST"], type="http_stream", response_model=dict, summary="List activities")
    async def query_activities(
        self,
        query: dict = None,
        search: str = None,
        host: str = None,
        domain: str = None,
        type: str = None,
        target_id: str = None,
        archived: bool = False,
        active: bool = True,
        ignored: bool = False,
        fields: list[str] = None,
        sort: list[str | tuple[str, int]] = None,
        aggregate: list[dict] = None,
    ):
        """
        Advanced querying of activities. Choose your own filters and fields.

        Args:
            query: Additional query parameters (mongo)
            search: Search using mongo's text index
            host: Filter activities by host (exact match only)
            domain: Filter activities by domain (subdomains allowed)
            type: Filter activities by type
            target_id: Filter activities by target ID
            archived: Optionally return archived activities
            active: Whether to include active (non-archived) activities
            fields: List of fields to return
            sort: Fields and direction to sort by. Accepts either a list of field names or a list of tuples (field, direction).
                E.g. sort=["-last_seen", "technology"] or sort=[("last_seen", -1), ("technology", 1)]
            aggregate: Optional custom MongoDB aggregation pipeline
        """
        query = dict(query or {})
        # this endpoint is only for findings, so we need to remove the type filter
        query.pop("type", None)
        query = await self._make_bbot_query(
            query=query,
            search=search,
            host=host,
            domain=domain,
            type=type,
            target_id=target_id,
            archived=archived,
            active=active,
        )
        async for activity in self._mongo_query(
            query=query,
            fields=fields,
            sort=sort,
            aggregate=aggregate,
        ):
            yield activity

    @api_endpoint("/tail", type="websocket_stream_outgoing", response_model=Activity)
    async def tail_activities(self, n: int = 0):
        agen = self.message_queue.tail_activities(n=n)
        try:
            async for activity in agen:
                yield activity
        finally:
            with suppress(BaseException):
                await agen.aclose()
