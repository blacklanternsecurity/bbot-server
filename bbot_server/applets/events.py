import json
from sqlmodel import select
from fastapi import WebSocket, HTTPException
from starlette.websockets import WebSocketDisconnect

from bbot_server.models import Event, Scan, Target
from bbot_server.applets._base import BaseApplet, api_endpoint


class Events(BaseApplet):

    data_model = Event
    include_apps = ["Subdomains"]

    @api_endpoint("/{event_id}", methods=["GET"], summary="Get events matching a single event ID")
    async def get_event(self, event_id: str) -> list[Event]:
        statement = select(self.model).where(self.model.id == event_id)
        return await self.db.find_many(statement)

    @api_endpoint("/", methods=["GET"], summary="Get Events")
    async def get_events(self) -> list[Event]:
        return await self.db.find_many()

    @api_endpoint("/get_event_chain/{event_uuid}", methods=["GET"])
    async def get_event_chain(self, event_uuid: int) -> list[Event]:
        event_statement = select(self.model).where(self.model.uuid == event_uuid)
        event = await self.db.exec(event_statement).first()
        if event is None:
            raise HTTPException(status_code=404, detail=f"No event found with id {event_uuid}")
        chain_statement = select(self.model).where(self.model.id.in_(event.parent_chain))
        return await self.db.find_many(chain_statement)

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
