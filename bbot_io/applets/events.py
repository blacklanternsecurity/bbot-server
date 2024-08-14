import json
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from bbot_io.models import Event, Scan, Target
from bbot_io.applets.base import BaseApplet, api_endpoint


class Events(BaseApplet):

    model = Event

    def _setup(self):
        self.include_app("Subdomains")

    @api_endpoint("/", methods=["GET"], summary="Get Events")
    async def get_events(self) -> list[Event]:
        return await self.db.find()

    @api_endpoint("/", methods=["POST", "PUT"], summary="Create Event")
    async def create_event(self, event: Event):
        if event.type == "SCAN":
            event_data = event.get_data()
            scan = Scan(**event_data)
            await self.parent.put_scan(scan)
            # target = Target(**event_data)
            # await self.parent.put_target(target)
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
