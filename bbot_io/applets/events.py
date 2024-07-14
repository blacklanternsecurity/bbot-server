import json
from sqlmodel import distinct, select
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from bbot_io.models import Event, Scan
from bbot_io.applets.base import BaseApplet, api_endpoint


class Events(BaseApplet):

    model = Event

    @api_endpoint("/put_event", methods=["POST", "PUT"])
    async def put_event(self, event: Event):
        if event.type == "SCAN":
            scan_data = event.get_data()
            scan = Scan(**scan_data)
            await self.parent.put_scan(scan)
        return await self.db.insert(event.validated)

    @api_endpoint("/get_events", methods=["GET"])
    async def get_events(self) -> list[Event]:
        return await self.db.find()

    @api_endpoint("/get_subdomains", methods=["GET"])
    async def get_subdomains(self) -> list[str]:
        statement = select(distinct(self.model.host))
        statement = statement.where(self.model.type == "DNS_NAME")
        return await self.db.exec(statement)

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
