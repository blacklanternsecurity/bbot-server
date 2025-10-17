import asyncio
from fastapi import Query, Body
from contextlib import suppress
from typing import AsyncGenerator, Annotated
from bbot_server.models.event_models import Event
from datetime import datetime, timezone, timedelta

from bbot_server.applets.base import BaseApplet, api_endpoint


class EventsApplet(BaseApplet):
    name = "Events"
    watched_events = ["*"]
    description = "query raw BBOT scan events"
    model = Event

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._archive_events_task = None

    async def handle_event(self, event: Event, asset):
        # write the event to the database
        await self.collection.insert_one(event.model_dump())

    @api_endpoint("/", methods=["POST"], summary="Insert a BBOT event into the asset database")
    async def insert_event(self, event: Event):
        """
        Insert a BBOT event into the asset database
        """
        # publish event to the message queue
        # it will be picked up by the watchdog and ingested
        await self.root.message_queue.publish_event(event)

    @api_endpoint("/get/{uuid}", methods=["GET"], summary="Get an event by its UUID")
    async def get_event(self, uuid: str) -> Event:
        event = await self.collection.find_one({"uuid": uuid})
        if event is None:
            raise self.BBOTServerNotFoundError(f"Event {uuid} not found")
        return self.model(**event)

    @api_endpoint("/list", methods=["GET"], type="http_stream", response_model=Event, summary="Stream all events")
    async def list_events(
        self,
        type: str = None,
        host: str = None,
        domain: str = None,
        scan: str = None,
        min_timestamp: float = None,
        max_timestamp: float = None,
        active: bool = True,
        archived: bool = False,
    ):
        async for event in self.mongo_iter(
            type=type,
            host=host,
            domain=domain,
            scan=scan,
            min_timestamp=min_timestamp,
            max_timestamp=max_timestamp,
            archived=archived,
            active=active,
        ):
            yield self.model(**event)

    @api_endpoint("/query", methods=["POST"], type="http_stream", response_model=dict, summary="Query findings")
    async def query_events(
        self,
        query: Annotated[dict, Body(description="Raw mongo query")] = None,
        search: Annotated[str, Body(description="Search using mongo's text index")] = None,
        host: Annotated[str, Body(description="Filter by exact hostname or IP address")] = None,
        domain: Annotated[str, Body(description="Filter by domain or subdomain")] = None,
        target_id: Annotated[str, Body(description="Filter by target name or id")] = None,
        archived: Annotated[bool, Body(description="Whether to include archived findings")] = False,
        active: Annotated[bool, Body(description="Whether to include active (non-archived) findings")] = True,
        min_timestamp: Annotated[float, Body(description="Filter by minimum timestamp")] = None,
        max_timestamp: Annotated[float, Body(description="Filter by maximum timestamp")] = None,
        fields: Annotated[list[str], Body(description="List of fields to return")] = None,
        limit: Annotated[int, Body(description="Limit the number of events returned")] = None,
        skip: Annotated[int, Body(description="Skip the first N events")] = None,
        sort: Annotated[list[str | tuple[str, int]], Body(description="Fields and direction to sort by")] = None,
        aggregate: Annotated[list[dict], Body(description="Optional custom MongoDB aggregation pipeline")] = None,
    ):
        """
        Advanced querying of events. Choose your own filters and fields.
        """
        async for event in self.mongo_iter(
            query=query,
            search=search,
            host=host,
            domain=domain,
            target_id=target_id,
            archived=archived,
            active=active,
            min_timestamp=min_timestamp,
            max_timestamp=max_timestamp,
            fields=fields,
            limit=limit,
            skip=skip,
            sort=sort,
            aggregate=aggregate,
        ):
            yield event

    @api_endpoint("/tail", type="websocket_stream_outgoing", response_model=Event)
    async def tail_events(self, n: int = 0):
        async for event in self.message_queue.tail_events(n=n):
            yield event

    @api_endpoint("/archive", methods=["POST"], summary="Archive old events")
    async def archive_old_events(
        self,
        older_than: Annotated[int, Query(description="Archive events older than this many days")],
    ):
        # cancel the current archiving task if one is in progress
        if self._archive_events_task is not None:
            self.log.info(f"Archive is already in progress, cancelling")
            self._archive_events_task.cancel()
            with suppress(BaseException):
                await asyncio.wait_for(self._archive_events_task, 0.5)
            self._archive_events_task = None
        self._archive_events_task = asyncio.create_task(self._archive_events(older_than=older_than))

    @api_endpoint(
        "/ingest", type="websocket_stream_incoming", response_model=Event, summary="Ingest events via websocket"
    )
    async def consume_event_stream(self, event_generator: AsyncGenerator[Event, None]):
        """
        Allows consuming of events via a websocket stream.

        This is used by the agent to send events to the server.
        """
        async for event in event_generator:
            await self.insert_event(event)

    async def _archive_events(self, older_than: int):
        archive_after = (datetime.now(timezone.utc) - timedelta(days=older_than)).timestamp()
        # archive old events
        # we use strict_collection to make sure all the writes complete before we return
        result = await self.strict_collection.update_many(
            {"timestamp": {"$lt": archive_after}, "archived": {"$ne": True}},
            {"$set": {"archived": True}},
        )
        self.log.info(f"Archived {result.modified_count} events")
        # refresh asset database
        await self.root.assets.refresh_assets()

    async def make_bbot_query(self, query: dict = None, scan: str = None, id: str = None, **kwargs):
        query = dict(query or {})
        if scan is not None and "scan" not in query:
            query["scan"] = scan
        if id is not None and "id" not in query:
            query["id"] = id
        return await super().make_bbot_query(query=query, **kwargs)
