import asyncio
import traceback
from typing import Dict
from websockets.server import WebSocketServerProtocol

from bbot_server.applets.agents.agent_models import AgentMessage


class ConnectionManager:
    """
    Manages connections and pending requests for agents
    """

    def __init__(self):
        # active connections - agent_id -> websocket
        self.active_connections: Dict[str, WebSocketServerProtocol] = {}
        # pending requests - request_id -> future
        self.pending_requests: Dict[str, asyncio.Future] = {}

    def is_connected(self, agent_id: str):
        return agent_id in self.active_connections

    async def loop(self, agent_id: str, websocket: WebSocketServerProtocol):
        try:
            await websocket.accept()
            self.active_connections[agent_id] = websocket
            while True:
                # Wait for responses from client
                message = await websocket.receive_json()
                request_id = message.get("request_id")
                # If this is a response to a pending request, resolve it
                if request_id in self.pending_requests:
                    future = self.pending_requests[request_id]
                    future.set_result(message)
                else:
                    yield message
        except Exception as e:
            self.log.error(f"Error in websocket loop: {e}")
            self.log.error(traceback.format_exc())
        finally:
            self.disconnect(agent_id)

    def disconnect(self, agent_id: str):
        self.active_connections.pop(agent_id, None)

    async def send_command(self, agent_id: str, command, **kwargs):
        """
        Send a command to the remote agent, and get the response
        """
        if agent_id not in self.active_connections:
            raise ValueError(f"Client {agent_id} not connected")

        message = AgentMessage(command=command, kwargs=kwargs)

        # Create future for the response
        future = asyncio.Future()
        self.pending_requests[message.request_id] = future
        try:
            # Send request to client
            await self.active_connections[agent_id].send_json(message.model_dump())
            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=10.0)
            return response
        except asyncio.TimeoutError:
            raise TimeoutError(f"Request to client {agent_id} timed out")
        finally:
            self.pending_requests.pop(message.request_id, None)