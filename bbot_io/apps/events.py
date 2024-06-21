import json
from typing import List
from fastapi import APIRouter, WebSocket

from bbot_io.modules import IO
from bbot_io.models import Event


class EventAPI:

    def __init__(self, io_module):
        self.io = IO(io_module)

        self.router = APIRouter()
        self.router.add_api_route("/insert", self.insert_event, methods=["POST"])
        self.router.add_api_route("/scans", self.get_scans, response_model=List[dict])
        self.router.add_api_route("/subdomains", self.get_subdomains, response_model=List[str])
        self.router.add_api_route("/events", self.get_events, response_model=List[Event])
        self.router.add_api_route("/drop", self.drop_database)
        self.router.add_api_websocket_route("/ws", self.websocket)

    async def insert_event(self, event: Event):
        await self.io.insert_event(event)

    async def websocket(self, websocket: WebSocket):
        await websocket.accept()
        while True:
            data = await websocket.receive_text()
            j = json.loads(data)
            print(j)
            event = Event(**j)
            await self.io.insert_event(event)

    async def get_scans(self):
        return await self.io.get_scans()

    async def get_subdomains(self):
        return await self.io.get_subdomains()

    async def get_events(self, limit: int = None):
        return await self.io.get_events(limit=limit)

    async def drop_database(self):
        return await self.io.drop_database()
