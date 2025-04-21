import orjson
import asyncio
import logging
import traceback
from typing import Dict
from pydantic import UUID4
from contextlib import suppress
from starlette.websockets import WebSocketDisconnect, WebSocket

from bbot_server.agent import VALID_AGENT_COMMANDS
from bbot_server.models.agent_models import AgentCommand, AgentResponse


class ConnectionManager:
    """
    On the server side, manages incoming connections and pending outgoing commands for agents

    This is needed because we only have one websocket channel for commands, but we need to be able
    to execute multiple concurrent commands. We do this by way of a unique request_id for each command.
    """

    def __init__(self):
        self.log = logging.getLogger("bbot_server.agent.connection_manager")
        # active connections - agent_id -> websocket
        self.active_connections: Dict[str, WebSocket] = {}
        # pending requests - request_id -> future
        self.pending_requests: Dict[str, asyncio.Future] = {}

    def is_connected(self, agent_id: UUID4):
        """
        Check if an agent is connected
        """
        return str(agent_id) in self.active_connections

    async def loop(self, agent_id: UUID4, websocket: WebSocket):
        """
        Loop for handling incoming messages from an agent
        """
        self.log.debug(f"Starting connection manager loop for agent {agent_id}")
        agent_id = str(agent_id)
        try:
            await websocket.accept()
            self.active_connections[agent_id] = websocket
            while True:
                try:
                    # Wait for responses from agent
                    message = await websocket.receive_bytes()
                    message = orjson.loads(message)
                    message = AgentResponse(**message)
                    # If this is a response to a pending request, resolve it
                    try:
                        future = self.pending_requests.pop(message.request_id)
                        future.set_result(message.response)
                    except KeyError:
                        # otherwise, yield the message to the caller
                        yield message
                except WebSocketDisconnect:
                    self.log.warning(f"Agent {agent_id} disconnected")
                    break
                except Exception as e:
                    self.log.error(f"Error in server-side websocket loop for agent {agent_id}: {e}")
                    self.log.error(traceback.format_exc())
                    if isinstance(e, (WebSocketDisconnect, asyncio.CancelledError)):
                        raise
        finally:
            self.log.debug(f"Stopping connection manager loop for agent {agent_id}")
            await self.disconnect(agent_id)

    async def disconnect(self, agent_id: UUID4):
        """
        Disconnect an agent
        """
        connection = self.active_connections.pop(str(agent_id), None)
        if connection:
            with suppress(Exception):
                await connection.close()

    async def execute_command(self, agent_id: UUID4, command: str, timeout=10, **kwargs) -> AgentResponse:
        """
        Executes a command on the remote agent, and returns the response
        """
        agent_id = str(agent_id)

        request = AgentCommand(command=command, kwargs=kwargs)

        # abort if agent isn't connected
        if not self.is_connected(agent_id):
            error = f"Client {agent_id} not connected"
            self.log.error(error)
            return AgentResponse(request_id=request.request_id, error=error)

        # make sure the command is valid
        # TODO: also validate the kwargs match its type hints
        if not command in VALID_AGENT_COMMANDS:
            error = f"Invalid command: {command}"
            self.log.error(error)
            return AgentResponse(request_id=request.request_id, error=error)

        # Create future for the response
        future = asyncio.Future()
        self.pending_requests[request.request_id] = future
        try:
            # Send request to client
            json_message = request.model_dump()

            # get the agent's websocket
            try:
                agent_websocket = self.active_connections[agent_id]
            except KeyError:
                error = f"Failed to execute command '{command}' on {agent_id}: agent not connected"
                self.log.error(error)
                return AgentResponse(request_id=request.request_id, error=error)

            # send the command to the agent
            try:
                # Serialize with orjson first
                message_bytes = orjson.dumps(json_message)
                # Use send_bytes instead of send_json
                await agent_websocket.send_bytes(message_bytes)
            except Exception as e:
                error = f"Failed to send command: {request} to {agent_id}: {e}"
                self.log.error(error)
                self.log.error(traceback.format_exc())
                return AgentResponse(request_id=request.request_id, error=error)

            # Wait for response with timeout
            try:
                response = await asyncio.wait_for(future, timeout=timeout)
                return AgentResponse(request_id=request.request_id, response=response)

            except Exception as e:
                error = f"Error waiting for response to command '{command}' on {agent_id}: {e}"
                trace = traceback.format_exc()
                self.log.error(error)
                self.log.error(trace)
                return AgentResponse(request_id=request.request_id, error=f"{error}\n{trace}")

        except asyncio.TimeoutError:
            error = f"Request to client {agent_id} timed out"
            self.log.error(error)
            return AgentResponse(request_id=request.request_id, error=error)

        finally:
            self.pending_requests.pop(request.request_id, None)
