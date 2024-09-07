import json
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from bbot_server.models import Event, Scan, Target
from bbot_server.applets._base import BaseApplet, api_endpoint


class Events(BaseApplet):

    model = Event
    include_apps = ["Subdomains"]

    @api_endpoint("/", methods=["GET"], summary="Get Events")
    async def get_events(self) -> list[Event]:
        return await self.db.find()

    # @api_endpoint("/chain/{event_id}", methods=["GET"], summary="Get Full Chain of Parents")
    # async def get_events(self, event_id: str) -> list[Event]:
    #     main_event = self.db.find()

    @api_endpoint("/", methods=["POST"], summary="Create Event")
    async def create_event(self, event: Event):
        if event.type == "SCAN":
            event_data = event.get_data()
            if not isinstance(event_data, dict):
                raise ValueError(f"Invalid data for SCAN event: {event_data}")
            scan = Scan(**event_data)
            await self.parent.put_scan(scan)
            target_data = event_data.get("target", {})
            if not isinstance(target_data, dict):
                raise ValueError(f"Invalid target for SCAN event: {target_data}")
            target = Target(**target_data)
            await self.parent.create_target(target)
        return await self.db.insert(event.validated)

    # @api_endpoint("/get_events", methods=["GET"])
    # async def get_event_chain(self, event_id: str) -> list[Event]:
    #     return await self.db.find()

    @api_endpoint("/ingest", type="websocket")
    async def websocket(self, websocket: WebSocket):
        await websocket.accept()
        while True:
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
                return
            j = json.loads(data)
            event = Event(**j)
            await self.io.insert_event(event.validated)
