import json
from uuid import UUID
from typing import Optional
from sqlmodel import select
from fastapi import WebSocket, HTTPException
from starlette.websockets import WebSocketDisconnect

from bbot_server.models import Event, ScanModel, Target
from bbot_server.applets._base import BaseApplet, api_endpoint


class Events(BaseApplet):

    description = "raw events directly from BBOT"
    data_model = Event

    @api_endpoint("/", methods=["GET"], summary="Get Events")
    async def get_events(self) -> list[Event]:
        """
        Get all events.
        """
        return await self.db.find_many()

    @api_endpoint("/host/{host}", methods=["GET"], summary="Get events by host")
    async def get_events_by_host(self, host: str) -> list[Event]:
        statement = select(self.model).where(self.model.host == host)
        return await self.db.find_many(statement)

    @api_endpoint("/", methods=["POST"], summary="Create Event")
    async def create_event(self, event: Event):
        """
        Create a new event.
        """
        ret = await self.db.insert(event)

        # if it's a SCAN event, create/update the scan and target
        if event.type == "SCAN":
            event_data = event.get_data()
            if not isinstance(event_data, dict):
                raise ValueError(f"Invalid data for SCAN event: {event_data}")
            scan = ScanModel(**event_data)
            await self.parent.put_scan(scan)

            target_data = event_data.get("target", {})
            if not isinstance(target_data, dict):
                raise ValueError(f"Invalid target for SCAN event: {target_data}")
            target = Target(**target_data)
            await self.parent.create_target(target)

        # update assets with this event
        await self.parent.update_asset(event)

        return ret

    @api_endpoint("/id/{event_id}", methods=["GET"], summary="Get events by ID")
    async def get_events_by_id(self, event_id: str) -> list[Event]:
        """
        Get events matching a single event ID.
        """
        statement = select(self.model).where(self.model.id == event_id)
        return await self.db.find_many(statement)

    @api_endpoint("/uuid/{event_uuid}", methods=["GET"], summary="Get event by UUID")
    async def get_event_by_uuid(self, event_uuid: UUID) -> Optional[Event]:
        """
        Get a single event by its UUID.
        """
        statement = select(self.model).where(self.model.uuid == event_uuid)
        return await self.db.find_one(statement)

    @api_endpoint("/parent_chain/{event_uuid}", methods=["GET"], summary="Get full chain of parent events")
    async def get_event_chain(self, event_uuid: int) -> list[Event]:
        """
        Get full chain of parent events leading to a certain event's discovery.
        """
        event_statement = select(self.model).where(self.model.uuid == event_uuid)
        event = await self.db.exec(event_statement).first()
        if event is None:
            raise HTTPException(status_code=404, detail=f"No event found with id {event_uuid}")
        chain_statement = select(self.model).where(self.model.id.in_(event.parent_chain))
        return await self.db.find_many(chain_statement)

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
            await self.io.insert_event(event)
