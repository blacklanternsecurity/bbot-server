import orjson
import asyncio
import logging
import websockets
from contextlib import suppress
from urllib.parse import urlparse, urlunparse

from bbot_server.config import BBOT_SERVER_CONFIG

default_server_url = BBOT_SERVER_CONFIG.get("url", "http://localhost:8807/v1/")


# decorator
def command(fn):
    fn._agent_command = True
    return fn


class BBOTAgent:
    def __init__(self, id: str, name: str, server_url: str = ""):
        self.log = logging.getLogger()
        self.id = id
        self.name = name
        self.server_url = server_url or default_server_url
        self.parsed_server_url = urlparse(self.server_url)
        self.websocket_scheme = "ws" if self.parsed_server_url.scheme == "http" else "wss"
        self.websocket_url = urlunparse(
            (
                self.websocket_scheme,
                self.parsed_server_url.netloc,
                f"{self.parsed_server_url.path.rstrip('/')}/scans/agents/dock/{self.id}",
                "",
                "",
                "",
            )
        )
        self.status = "READY"

    async def start(self):
        self.agent_task = asyncio.create_task(self._run())

    async def stop(self):
        self.agent_task.cancel()
        with suppress(asyncio.CancelledError):
            await self.agent_task

    async def _run(self):
        while True:
            try:
                self.log.info(f"Connecting to {self.websocket_url}")
                async with websockets.connect(self.websocket_url) as websocket:
                    while True:
                        message = await websocket.recv()
                        self.log.info(f"Received message: {message}")
                        await websocket.send(message)
            except websockets.ConnectionClosed:
                self.log.warning("Connection closed, attempting to reconnect...")
                await asyncio.sleep(1)  # Wait before retrying
            except Exception as e:
                self.log.error(f"Unexpected error: {e}")
                await asyncio.sleep(1)  # Wait before retrying

    @command
    async def start_scan(self):
        pass
