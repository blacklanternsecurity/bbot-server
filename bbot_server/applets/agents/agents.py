import time
import asyncio
import traceback
from pydantic import UUID4
from fastapi import WebSocket
from contextlib import suppress
from datetime import datetime, timezone
from bbot_server.applets.agents.agent_models import Agent
from bbot_server.applets._base import BaseApplet, api_endpoint


# TODO: will multiple uvicorn workers break this?
# does only one of them have access to the active websocket connections?


class AgentsApplet(BaseApplet):
    name = "Agents"
    description = "manage BBOT scan agents"
    model = Agent

    async def setup(self):
        # if this is the main server instance,
        if self.root.is_main_server:
            from bbot_server.connectionmanager import ConnectionManager

            # manage incoming agent connections
            self.connection_manager = ConnectionManager()
            # watch the
            self.kickoff_queued_scans_task = self.create_task(self._kickoff_queued_scans_loop())

    @api_endpoint("/list", methods=["GET"], summary="List all agents")
    async def get_agents(self) -> list[Agent]:
        db_results = await self.collection.find().to_list(length=None)
        agents = []
        for agent in db_results:
            agent = await self._make_agent(agent)
            agents.append(agent)
        return agents

    @api_endpoint("/", methods=["POST"], summary="Create an agent")
    async def create_agent(self, name: str, description: str = "") -> Agent:
        agent = Agent(name=name, description=description)
        try:
            await self.collection.insert_one(agent.model_dump())
        except Exception as e:
            raise self.BBOTServerError(f"Error creating agent {name}: {e}") from e
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
        return await self._make_agent(agent)

    @api_endpoint("/status", methods=["GET"], summary="Get the status of an agent")
    async def get_agent_status(self, id: UUID4) -> dict[str, str]:
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
        agents = await self.collection.find({"status": status}).to_list(length=None)
        agents = [Agent(**agent) for agent in agents]
        return agents

    async def execute_command(self, agent_id: UUID4, command: str, **kwargs) -> dict:
        # since this is communicating directly with a connected agent over websocket,
        # it must be called from the main bbot server instance
        self.ensure_main_server()
        ret = await self.connection_manager.execute_command(str(agent_id), command, **kwargs)
        return ret

    @api_endpoint("/dock/{agent_id}", type="websocket")
    async def dock(self, websocket: WebSocket, agent_id: UUID4):
        """
        The main websocket endpoint where agents connect
        """
        self.ensure_main_server()
        self.log.warning(f"Agent {agent_id} initiated docking procedure")

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

        self.log.info(f"Agent {agent.name} connected")
        await self._on_connect(agent)
        # this loop handles gratuitous messages from the agent (i.e. messages that are not responses to commands)
        try:
            async for message in self.connection_manager.loop(agent.id, websocket):
                self.log.info(f"Server received gratuitous message from agent {agent.name}: {message}")
                if list(message.response) == ["status"]:
                    await self._update_agent_status(agent.id, message.response["status"], True)

        except Exception as e:
            self.log.error(f"Error in server-side websocket loop for agent {agent.id}: {e}")
            self.log.error(traceback.format_exc())

        finally:
            self.log.warning(f"Agent {agent.name} disconnected")
            await self._on_disconnect(agent)

    async def _on_connect(self, agent):
        await self._update_agent_status(agent.id, "ONLINE", True)
        await self.emit_activity(
            type="AGENT_CONNECTED",
            detail={"agent_id": str(agent.id)},
            description=f"Agent [dark_orange]{agent.name}[/dark_orange] connected",
        )

    async def _on_disconnect(self, agent):
        await self._update_agent_status(agent.id, "OFFLINE", False)
        await self.emit_activity(
            type="AGENT_DISCONNECTED",
            detail={"agent_id": str(agent.id)},
            description=f"Agent [dark_orange]{agent.name}[/dark_orange] disconnected",
        )

    async def _update_agent_status(self, agent_id: UUID4, status: str, connected: bool):
        now = datetime.now(timezone.utc).timestamp()
        await self.collection.update_one(
            {"id": str(agent_id)},
            {
                "$set": {
                    "status": status,
                    "connected": connected,
                    "last_seen": now,
                }
            },
        )

    async def _refresh_agent_status(self, agent: Agent):
        """
        Checks the 'connected' status of the agent and updates its last_seen timestamp if needed
        """
        if agent.connected:
            now = datetime.now(timezone.utc).timestamp()
            agent.last_seen = now
        await self.collection.update_one({"id": str(agent.id)}, {"$set": agent.model_dump()})
        return agent

    async def _make_agent(self, agent_dict: dict):
        agent = Agent(**agent_dict)
        agent = await self._refresh_agent_status(agent)
        return agent

    async def _kickoff_queued_scans(self):
        return 0

    async def _kickoff_queued_scans_loop(self):
        for i in range(1000):
            online_agents = await self.get_online_agents()
            online_agents = [str(agent.id) for agent in online_agents]
            if not online_agents:
                await self.sleep(1)
                continue
            now = datetime.now(timezone.utc).timestamp()
            await self.collection.update_many({"id": {"$in": online_agents}}, {"$set": {"last_seen": now}})
            scans_started = await self._kickoff_queued_scans()
            if not scans_started:
                await self.sleep(1)

    async def cleanup(self):
        if self.is_main_server:
            self.kickoff_queued_scans_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.kickoff_queued_scans_task
