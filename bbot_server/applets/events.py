from contextlib import suppress

from bbot.models.pydantic import Event
from bbot_server.models.assets import AssetActivity
from bbot_server.applets._base import BaseApplet, api_endpoint


class Events(BaseApplet):
    description = "events"

    @api_endpoint("/", methods=["POST"], summary="Insert a BBOT event into the asset database")
    async def insert_event(self, event: Event) -> list[AssetActivity]:
        """
        Insert a BBOT event into the asset database

        This creates a list of activities that occurred as a result of the event (e.g. PORT_OPENED, CRITICAL_VULN, etc.).

        The activities are raised to subscribers and also returned to the caller.
        """
        # publish event to the message queue
        await self.root.message_queue.event_publish(event.model_dump())
        # ingest it into the asset database
        activities = await self.root.assets.process_new_event(event)
        return activities

    @api_endpoint("/", methods=["GET"], summary="Get all events")
    async def get_events(self) -> list[Event]:
        events = await self.event_store.get_events()
        return events

    @api_endpoint("/{uuid}", methods=["GET"], summary="Get an event by its UUID")
    async def get_event(self, uuid: str) -> dict:
        print("GETTING EVENT", uuid)

    @api_endpoint("/tail", type="websocket")
    async def tail_events(self):
        agen = self.message_queue.event_tail()
        try:
            async for event in agen:
                yield event
        finally:
            with suppress(Exception):
                await agen.aclose()
