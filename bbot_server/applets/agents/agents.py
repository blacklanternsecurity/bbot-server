import asyncio
import traceback
from typing import Any
from pydantic import UUID4
from fastapi import WebSocket
from contextlib import suppress
from datetime import datetime, timezone
from bbot_server.applets.agents.agent_models import Agent
from bbot_server.applets._base import BaseApplet, api_endpoint
from bbot_server.applets.agents.connectionmanager import ConnectionManager


class AgentsApplet(BaseApplet):
    name = "Agents"
    description = "manage BBOT scan agents"
    model = Agent

    async def setup(self):
        self.connection_manager = ConnectionManager()
        # we only kick off scans from the main server instance
        if self.root.is_main_server:
            self.kickoff_queued_scans_task = self.create_task(self._kickoff_queued_scans_loop())

    def _make_agent(self, agent: Agent):
        agent = Agent(**agent)
        if self.connection_manager.is_connected(agent.id):
            agent.connected = True
            agent.last_seen = datetime.now(timezone.utc).timestamp()
        return agent

    @api_endpoint("/list", methods=["GET"], summary="List all agents")
    async def get_agents(self) -> list[Agent]:
        db_results = await self.collection.find().to_list(length=None)
        agents = []
        for agent in db_results:
            agent = self._make_agent(agent)
            agents.append(agent)
        return agents

    @api_endpoint("/", methods=["POST"], summary="Create an agent")
    async def create_agent(self, name: str, description: str = "") -> Agent:
        agent = Agent(name=name, description=description)
        await self.collection.insert_one(agent.model_dump())
        return agent

    @api_endpoint("/", methods=["GET"], summary="Get an agent by its id")
    async def get_agent(self, id: UUID4 = None, name: str = None) -> Agent:
        if id is None and name is None:
            raise ValueError("Either id or name must be provided")
        query = {}
        if id is not None:
            query["id"] = str(id)
        if name is not None:
            query["name"] = name
        agent = await self.collection.find_one(query)
        if agent is None:
            raise self.BBOTServerNotFoundError(f"Agent not found")
        return self._make_agent(agent)

    @api_endpoint("/status", methods=["GET"], summary="Get the status of an agent")
    async def get_agent_status(self, id: UUID4) -> dict[str, str]:
        import time

        start_time = time.time()
        try:
            command_response = await self.connection_manager.execute_command(str(id), "status", timeout=10)
            if command_response.error:
                raise self.BBOTServerValueError(command_response.error)
            agent_status = command_response.response
        except TimeoutError:
            end_time = time.time()
            self.log.error(f"Timed out after {end_time - start_time:.2f}s getting agent status for {id}")
            agent_status = {"status": "TIMEOUT"}
        except (KeyError, self.BBOTServerValueError) as e:
            self.log.error(f"Failed to get agent status for {id}: {e}")
            agent_status = {"status": "OFFLINE"}
        return agent_status

    @api_endpoint("/online", methods=["GET"], summary="Get all online agents")
    async def get_online_agents(self, status: str = "READY") -> list[Agent]:
        agents = []
        for agent_id in self.connection_manager.active_connections:
            agent = await self.get_agent(id=agent_id)
            if agent and (status is None or agent.status == status):
                agents.append(agent)
        return agents

    async def execute_command(self, agent_id: UUID4, command: str, **kwargs) -> dict:
        return await self.connection_manager.execute_command(str(agent_id), command, **kwargs)

    @api_endpoint("/dock/{agent_id}", type="websocket")
    async def dock(self, websocket: WebSocket, agent_id: UUID4):
        """
        The main websocket endpoint where agents connect
        """
        self.log.info(f"Agent {agent_id} initiated docking procedure")

        # reject any connection without a valid agent id
        agent = await self.get_agent(id=str(agent_id))
        if agent is None:
            reason = f"Unknown agent {agent_id} tried to connect"
            self.log.warning(reason)
            await websocket.close(code=3000, reason=reason)
            return

        # reject connections from agents that are already connected
        if self.connection_manager.is_connected(agent.id):
            reason = f"Agent {agent.name} already connected"
            self.log.warning(reason)
            await websocket.close(code=1013, reason=reason)
            return

        await self.emit_activity(
            type="AGENT_CONNECTED",
            detail={"agent_id": str(agent.id)},
            description=f"Agent [dark_orange]{agent.name}[/dark_orange] connected",
        )

        self.log.info(f"Agent {agent.name} connected")
        # this loop handles gratuitous messages from the agent (i.e. messages that are not responses to commands)
        try:
            async for message in self.connection_manager.loop(agent.id, websocket):
                self.log.info(f"Server received gratuitous message from agent {agent.name}: {message}")
                if list(message.response) == ["status"]:
                    await self._update_agent_status(agent.id, message.response["status"])

        except Exception as e:
            self.log.error(f"Error in server-side websocket loop for agent {agent.id}: {e}")
            self.log.error(traceback.format_exc())

        finally:
            self.log.warning(f"Agent {agent.name} disconnected")
            await self._update_agent_status(agent.id, "OFFLINE")
            await self.emit_activity(
                type="AGENT_DISCONNECTED",
                detail={"agent_id": str(agent.id)},
                description=f"Agent [dark_orange]{agent.name}[/dark_orange] disconnected",
            )

    async def _update_agent_status(self, agent_id: UUID4, status: str):
        now = datetime.now(timezone.utc).timestamp()
        await self.collection.update_one({"id": str(agent_id)}, {"$set": {"status": status, "last_seen": now}})

    async def _kickoff_queued_scans(self):
        return 0

    async def _kickoff_queued_scans_loop(self):
        while True:
            online_agents = await self.get_online_agents()
            online_agents = [str(agent.id) for agent in online_agents]
            if not online_agents:
                await self.sleep(5)
                continue
            now = datetime.now(timezone.utc).timestamp()
            await self.collection.update_many({"id": {"$in": online_agents}}, {"$set": {"last_seen": now}})
            scans_started = await self._kickoff_queued_scans()
            if not scans_started:
                await self.sleep(1)

    async def cleanup(self):
        update_agents_last_seen = getattr(self, "update_agents_last_seen_task", None)
        if update_agents_last_seen is not None:
            update_agents_last_seen.cancel()
            with suppress(self.CancelledError):
                await update_agents_last_seen
