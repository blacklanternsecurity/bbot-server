import json
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder

from bbot.models.pydantic import Event
from bbot_server.models.assets import AssetActivity
from bbot_server.applets._base import BaseApplet, api_endpoint, watchdog_task


class EventsApplet(BaseApplet):
    name = "Events"
    description = "query raw BBOT scan events"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # set up cron job for archiving events
        # self.archive_cron = self.event_store.event_store_config.archive_cron

    @api_endpoint("/", methods=["POST"], summary="Insert a BBOT event into the asset database")
    async def insert_event(self, event: Event):
        """
        Insert a BBOT event into the asset database

        This creates a list of activities that occurred as a result of the event (e.g. PORT_OPENED, CRITICAL_VULN, etc.).

        The activities are raised to subscribers and also returned to the caller.
        """
        # publish event to the message queue
        # it will be picked up by the watchdog and ingested
        await self.root.message_queue.event_publish(event)

    # @api_endpoint("/", methods=["GET"], summary="Get all events")
    # async def get_events(self, archived: bool = None):
    #     async for event in self.event_store.get_events(archived=archived):
    #         yield event.model_dump()
    #     # events = await self.event_store.get_events(archived=archived)
    #     # return events

    @api_endpoint("/{uuid}", methods=["GET"], summary="Get an event by its UUID")
    async def get_event(self, uuid: str) -> dict:
        print("GETTING EVENT", uuid)

    @api_endpoint("/tail", type="websocket", response_model=Event)
    async def tail_events(self):
        async for event in self.message_queue.event_tail():
            yield event

    @api_endpoint("/{uuid}/archive", methods=["GET"], summary="Archive an event")
    async def archive_event(self, uuid: str):
        await self.event_store.archive_event(uuid)

    @api_endpoint("/archive", methods=["GET"], summary="Archive old events")
    async def archive_old_events(self, older_than=None):
        # first, archive old events
        await self.event_store.archive_events(older_than=older_than)
        # then, refresh all assets
        await self.root.assets.refresh_assets()

    # TODO: offload archive task to watchdog
    @watchdog_task()
    async def archive_events_task(self):
        await self.event_store.archive_events()

    @api_endpoint("/", methods=["GET"], type="stream", response_model=Event, summary="Stream all events")
    async def get_events(self, type: str = None, archived: bool = False, active: bool = True):
        async for event in self.event_store.get_events(type=type, archived=archived, active=active):
            yield event
