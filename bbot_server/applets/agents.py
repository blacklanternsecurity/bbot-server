import uuid
from typing import Annotated
from contextlib import suppress
from pydantic import Field, UUID4
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect
from bbot_server.models.base import BaseBBOTServerModel
from bbot_server.applets._base import BaseApplet, api_endpoint


class Agent(BaseBBOTServerModel):
    __tablename__ = "agents"
    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=uuid.uuid4)
    name: Annotated[str, "indexed", "unique"]
    description: str
    connected: Annotated[bool, "indexed"] = False
    status: Annotated[str, "indexed"] = "OFFLINE"
    last_seen: Annotated[float, "indexed"] = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class AgentMessage(BaseBBOTServerModel):
    command: str
    kwargs: dict


class AgentsApplet(BaseApplet):
    name = "Agents"
    description = "manage BBOT scan agents"
    model = Agent

    async def setup(self):
        self.connected_agents = {}
        self.update_agents_last_seen_task = self.create_task(self._update_agents_last_seen())

    def _make_agent(self, agent: Agent):
        agent = Agent(**agent)
        if agent.id in self.connected_agents:
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
    async def get_agent(self, id: str = None, name: str = None) -> Agent:
        if id is None and name is None:
            raise ValueError("Either id or name must be provided")
        query = {}
        if id is not None:
            query["id"] = str(id)
        if name is not None:
            query["name"] = name
        agent = await self.collection.find_one(query)
        if agent is None:
            return None
        return self._make_agent(agent)

    @api_endpoint("/online", methods=["GET"], summary="Get all online agents")
    async def get_online_agents(self, status: str = None) -> list[Agent]:
        agents = []
        for agent_id in getattr(self, "connected_agents", []):
            agent = await self.get_agent(id=agent_id)
            if agent and (status is None or agent.status == status):
                agents.append(agent)
        return agents

    async def send_message(self, agent_id: str, message: AgentMessage):
        if agent_id not in self.connected_agents:
            raise ValueError("Agent not connected")
        await self.connected_agents[agent_id].send_json(message.model_dump())

    @api_endpoint("/dock/{agent_id}", type="websocket")
    async def dock(self, websocket: WebSocket, agent_id: str):
        """
        The main websocket endpoint where agents connect
        """
        # reject any connection without a valid agent id
        agent = await self.get_agent(id=agent_id)
        if agent is None:
            self.log.warning(f"Unknown agent {agent_id} tried to connect")
            await websocket.close()
            return

        # reject connections from agents that are already connected
        if agent.id in self.connected_agents:
            self.log.warning(f"Agent {agent.name} already connected")
            await websocket.close()
            return

        try:
            await websocket.accept()  # Accept the WebSocket connection
            self.connected_agents[agent.id] = websocket
            self.log.info(f"Agent {agent.name} connected: {self.connected_agents}")
            now = datetime.now(timezone.utc).timestamp()
            await self.collection.update_one({"id": str(agent.id)}, {"$set": {"last_seen": now}})
            await self.emit_activity(
                type="AGENT_CONNECTED",
                description=f"Agent [dark_orange]{agent.name}[/dark_orange] connected",
            )

            while True:
                # Receive a message from the client
                data = await websocket.receive_text()

                # Process the received message and prepare a response
                response = f"Received: {data}"

                # Send a response back to the client
                await websocket.send_text(response)
        except WebSocketDisconnect:
            self.log.warning(f"Agent {agent.name} disconnected")
            await self.collection.update_one({"id": str(agent.id)}, {"$set": {"status": "OFFLINE"}})
            # self.connected_agents.pop(agent.id, None)
            await self.emit_activity(
                type="AGENT_DISCONNECTED",
                description=f"Agent [dark_orange]{agent.name}[/dark_orange] disconnected",
            )

    async def _update_agents_last_seen(self):
        while True:
            online_agents = await self.get_online_agents()
            online_agents = [str(agent.id) for agent in online_agents]
            now = datetime.now(timezone.utc).timestamp()
            await self.collection.update_many({"id": {"$in": online_agents}}, {"$set": {"last_seen": now}})
            await self.sleep(5)

    async def cleanup(self):
        self.update_agents_last_seen_task.cancel()
        with suppress(self.CancelledError):
            await self.update_agents_last_seen_task
