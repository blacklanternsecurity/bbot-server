import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Annotated, AsyncGenerator

from fastapi import Query
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from bbot.models.pydantic import Event as BBOTEvent
from bbot_server.applets.base import BaseApplet, api_endpoint
from bbot_server.modules.events.events_models import EventsQuery, Event


class EventsApplet(BaseApplet):
    name = "Events"
    watched_events = ["*"]
    description = "query raw BBOT scan events"
    model = Event

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._archive_events_task = None

    async def handle_event(self, event, host):
        # construct our Event from bbot's Event dict
        d = event.model_dump()
        # compute reverse_host
        host = d.get("host")
        if host:
            d["reverse_host"] = str(host)[::-1]
        # ensure data is string
        if "data" in d and d["data"] is not None:
            d["data"] = str(d["data"])
        # only keep fields that exist in our model
        valid_fields = set(Event.model_fields.keys())
        d = {k: v for k, v in d.items() if k in valid_fields}
        d.pop("pk", None)
        db_event = Event(**d)
        try:
            await self._insert(db_event)
        except IntegrityError:
            pass  # duplicate uuid, skip

    @api_endpoint("/", methods=["POST"], summary="Insert a BBOT event into the asset database")
    async def insert_event(self, event: BBOTEvent):
        """
        Insert a BBOT event into the asset database
        """
        # publish event to the message queue
        # it will be picked up by the watchdog and ingested
        await self.root.message_queue.publish_event(event)

    @api_endpoint("/get/{uuid}", methods=["GET"], summary="Get an event by its UUID")
    async def get_event(self, uuid: str) -> Event:
        event = await self._get_one(uuid=uuid)
        if event is None:
            raise self.BBOTServerNotFoundError(f"Event {uuid} not found")
        return event

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
        query = EventsQuery(
            type=type,
            host=host,
            domain=domain,
            scan=scan,
            min_timestamp=min_timestamp,
            max_timestamp=max_timestamp,
            active=active,
            archived=archived,
            sort=[("pk", 1)],
        )
        async for row in query.query_iter(self):
            yield row

    @api_endpoint("/query", methods=["POST"], type="http_stream", response_model=dict, summary="Query events")
    async def query_events(self, query: EventsQuery | None = None):
        """
        Advanced querying of events. Choose your own filters and fields.
        """
        async for row in query.query_iter(self):
            d = row.model_dump()
            if query.fields:
                d = {k: v for k, v in d.items() if k in query.fields}
                d["_id"] = None  # backward compat
            yield d

    @api_endpoint("/count", methods=["POST"], summary="Count events")
    async def count_events(self, query: EventsQuery | None = None) -> int:
        """
        Same as query_events, except only returns the count
        """
        return await query.query_count(self)

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
        "/ingest", type="websocket_stream_incoming", response_model=BBOTEvent, summary="Ingest events via websocket"
    )
    async def consume_event_stream(self, event_generator: AsyncGenerator[BBOTEvent, None]):
        """
        Allows consuming of events via a websocket stream.

        This is used by the agent to send events to the server.
        """
        async for event in event_generator:
            await self.insert_event(event)

    async def _archive_events(self, older_than: int):
        archive_after = (datetime.now(timezone.utc) - timedelta(days=older_than)).timestamp()
        async with self.session() as session:
            stmt = (
                update(Event)
                .where(Event.timestamp < archive_after, Event.archived != True)
                .values(archived=True)
            )
            result = await session.execute(stmt)
            await session.commit()
            self.log.info(f"Archived {result.rowcount} events")
        # refresh asset database
        await self.root.assets.refresh_assets()
