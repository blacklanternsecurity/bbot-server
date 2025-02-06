from contextlib import suppress

from bbot.models.pydantic import Event
from bbot_server.models.assets import AssetActivity
from bbot_server.applets._base import BaseApplet, api_endpoint


class EventsApplet(BaseApplet):
    name = "Events"
    description = "query raw BBOT scan events"

    @api_endpoint("/", methods=["POST"], summary="Insert a BBOT event into the asset database")
    async def insert_event(self, event: Event) -> list[AssetActivity]:
        """
        Insert a BBOT event into the asset database

        This creates a list of activities that occurred as a result of the event (e.g. PORT_OPENED, CRITICAL_VULN, etc.).

        The activities are raised to subscribers and also returned to the caller.
        """
        # publish event to the message queue
        # it will be picked up by the watchdog and ingested
        await self.root.message_queue.event_publish(event)

    @api_endpoint("/", methods=["GET"], summary="Get all events")
    async def get_events(self) -> list[Event]:
        events = await self.event_store.get_events()
        return events

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
