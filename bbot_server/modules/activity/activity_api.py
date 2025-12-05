from fastapi import Body
from typing import Annotated
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
        query: Annotated[dict, Body(description="Raw mongo query")] = None,
        search: Annotated[
            str, Body(description="A human-friendly text search (will be ANDed with other filters)")
        ] = None,
        host: Annotated[str, Body(description="Filter activities by host (exact match only)")] = None,
        domain: Annotated[str, Body(description="Filter activities by domain (subdomains allowed)")] = None,
        type: Annotated[str, Body(description="Filter activities by type")] = None,
        target_id: Annotated[str, Body(description="Filter activities by target ID")] = None,
        archived: Annotated[bool, Body(description="Whether to include archived activities")] = False,
        active: Annotated[bool, Body(description="Whether to include active activities")] = True,
        fields: Annotated[list[str], Body(description="List of fields to return")] = None,
        limit: Annotated[int, Body(description="Limit the number of activities returned")] = None,
        skip: Annotated[int, Body(description="Skip the first N activities")] = None,
        sort: Annotated[list[str | tuple[str, int]], Body(description="Fields and direction to sort by")] = None,
        aggregate: Annotated[list[dict], Body(description="Optional custom MongoDB aggregation pipeline")] = None,
    ):
        """
        Advanced querying of activities. Choose your own filters and fields.
        """
        async for activity in self.mongo_iter(
            query=query,
            search=search,
            host=host,
            domain=domain,
            type=type,
            target_id=target_id,
            archived=archived,
            active=active,
            fields=fields,
            limit=limit,
            skip=skip,
            sort=sort,
            aggregate=aggregate,
        ):
            yield activity

    @api_endpoint("/count", methods=["POST"], summary="Count activities")
    async def count_activities(
        self,
        query: Annotated[dict, Body(description="Raw mongo query")] = None,
        search: Annotated[
            str, Body(description="A human-friendly text search (will be ANDed with other filters)")
        ] = None,
        host: Annotated[str, Body(description="Filter activities by host (exact match only)")] = None,
        domain: Annotated[str, Body(description="Filter activities by domain (subdomains allowed)")] = None,
        type: Annotated[str, Body(description="Filter activities by type")] = None,
        target_id: Annotated[str, Body(description="Filter activities by target ID")] = None,
        archived: Annotated[bool, Body(description="Whether to include archived activities")] = False,
        active: Annotated[bool, Body(description="Whether to include active activities")] = True,
    ) -> int:
        """
        Same as query_activities, except only returns the count
        """
        return await self.mongo_count(
            query=query,
            search=search,
            host=host,
            domain=domain,
            type=type,
            target_id=target_id,
            archived=archived,
            active=active,
        )

    @api_endpoint("/tail", type="websocket_stream_outgoing", response_model=Activity)
    async def tail_activities(self, n: int = 0):
        agen = self.message_queue.tail_activities(n=n)
        try:
            async for activity in agen:
                yield activity
        finally:
            with suppress(BaseException):
                await agen.aclose()
