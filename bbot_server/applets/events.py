from typing import AsyncGenerator
from bbot.models.pydantic import Event
from datetime import datetime, timezone, timedelta
from bbot_server.applets._base import BaseApplet, api_endpoint, watchdog_task


class EventsApplet(BaseApplet):
    name = "Events"
    watched_events = ["*"]
    description = "query raw BBOT scan events"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # set up cron job for archiving events
        # self.archive_cron = self.event_store.event_store_config.archive_cron

    async def handle_event(self, event: Event, asset):
        # write the event to the database
        await self.event_store.insert_event(event)

    @api_endpoint("/", methods=["POST"], summary="Insert a BBOT event into the asset database")
    async def insert_event(self, event: Event):
        """
        Insert a BBOT event into the asset database

        This creates a list of activities that occurred as a result of the event (e.g. PORT_OPENED, CRITICAL_VULN, etc.).

        The activities are raised to subscribers and also returned to the caller.
        """
        # publish event to the message queue
        # it will be picked up by the watchdog and ingested
        await self.root.message_queue.publish_event(event)

    @api_endpoint("/{uuid}", methods=["GET"], summary="Get an event by its UUID")
    async def get_event(self, uuid: str) -> Event:
        return await self.event_store.get_event(uuid)

    @api_endpoint("/tail", type="websocket_stream_outgoing", response_model=Event)
    async def tail_events(self, n: int = 0):
        async for event in self.message_queue.tail_events(n=n):
            yield event

    @api_endpoint("/{uuid}/archive", methods=["GET"], summary="Archive an event")
    async def archive_event(self, uuid: str):
        await self.event_store.archive_event(uuid)

    @api_endpoint("/archive", methods=["GET"], summary="Archive old events")
    async def archive_old_events(self, older_than=None):
        await self.archive_events_task.kiq()

    # TODO: run this whenever a scan finishes
    @watchdog_task(
        # # run every day at midnight
        # cron="0 0 * * *",
        # cron_config_key="event_store.archive_cron",
    )
    async def archive_events_task(self):
        archive_after = (datetime.now(timezone.utc) - timedelta(days=self.event_store.archive_after_days)).timestamp()
        # archive old events
        await self.event_store.archive_events(older_than=archive_after)
        # refresh asset database
        await self.root.assets.refresh_assets()

    @api_endpoint("/", methods=["GET"], type="http_stream", response_model=Event, summary="Stream all events")
    async def get_events(self, type: str = None, archived: bool = False, active: bool = True):
        async for event in self.event_store.get_events(type=type, archived=archived, active=active):
            yield event

    @api_endpoint(
        "/insert", type="websocket_stream_incoming", response_model=Event, summary="Insert events via websocket"
    )
    async def consume_event_stream(self, event_generator: AsyncGenerator[Event, None]):
        """
        Allows consuming of events via a websocket stream.

        This is used by the agent to send events to the server.
        """
        async for event in event_generator:
            # we use "interface" here because we need it to still work even if we're accessing a remote BBOT server instance
            # wait what?? TODO
            await self.interface.insert_event(event)
