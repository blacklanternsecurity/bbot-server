import orjson
import asyncio
import traceback
import websockets
from contextlib import suppress
from tests.test_applets.base import BaseAppletTest
from bbot_server.modules.agents.agents_models import AgentCommand, AgentResponse

import bbot_server.config as bbcfg


class TestAppletAgents(BaseAppletTest):
    needs_agent = True

    async def setup(self):
        agents = await self.bbot_server.get_agents()
        assert len(agents) == 1

        new_agent_2 = await self.bbot_server.create_agent(name="test_agent_2", description="test description 2")
        assert new_agent_2.name == "test_agent_2"
        assert new_agent_2.description == "test description 2"
        assert new_agent_2.id is not None

        agents = await self.bbot_server.get_agents()
        assert len(agents) == 2
        assert any(agent.id == new_agent_2.id for agent in agents)

        new_agent_3 = await self.bbot_server.create_agent(name="test_agent_3", description="test description 3")
        assert new_agent_3.name == "test_agent_3"
        assert new_agent_3.description == "test description 3"
        assert new_agent_3.id is not None
        assert new_agent_3.id != new_agent_2.id

        agents = await self.bbot_server.get_agents()
        assert len(agents) == 3
        assert any(agent.id == new_agent_3.id for agent in agents)
        assert any(agent.id == new_agent_2.id for agent in agents)

        agent_2 = await self.bbot_server.get_agent(new_agent_2.id)
        assert agent_2 is not None
        assert agent_2.name == new_agent_2.name
        assert agent_2.description == new_agent_2.description
        assert agent_2.id == new_agent_2.id

        agent_3 = await self.bbot_server.get_agent(new_agent_3.name)
        assert agent_3 is not None
        assert agent_3.name == new_agent_3.name
        assert agent_3.description == new_agent_3.description
        assert agent_3.id == new_agent_3.id

        # delete agent 2
        await self.bbot_server.delete_agent(agent_2.name)
        agents = await self.bbot_server.get_agents()
        assert len(agents) == 2
        assert not any(agent.id == agent_2.id for agent in agents)

        self.agent_3 = agent_3

    async def after_scan_1(self):
        # we only run this test if we're using the HTTP interface
        if self.bbot_server.interface_type != "http":
            return

        # our agent should be offline
        agent_status = await self.bbot_server.get_agent_status(self.agent_3.id)
        assert agent_status == {"agent_status": "OFFLINE", "scan_status": "UNKNOWN"}

        # the main test agent should be online
        connected_agents = await self.bbot_server.get_online_agents()
        assert len(connected_agents) == 1

        # sample agent just responds to status commands
        async def agent_dummy():
            # connect to the agent, send a message, and disconnect
            agent_url = f"ws://localhost:8807/v1/scans/agents/dock/{self.agent_3.id}"
            try:
                async for websocket in websockets.connect(
                    agent_url, additional_headers={bbcfg.API_KEY_NAME: bbcfg.get_api_key()}
                ):
                    gratuitous_status = AgentResponse(response={"agent_status": "READY", "scan_status": "NOT_RUNNING"})
                    await websocket.send(orjson.dumps(gratuitous_status.model_dump()))

                    while True:
                        # obligatory status command
                        status_command = await websocket.recv()
                        status_command = orjson.loads(status_command)
                        status_command = AgentCommand(**status_command)

                        assert status_command.command == "get_agent_status"
                        assert status_command.kwargs == {"detailed": False}
                        assert status_command.request_id

                        response = AgentResponse(
                            request_id=status_command.request_id,
                            response={"agent_status": "READY", "scan_status": "NOT_RUNNING"},
                        )
                        await websocket.send(orjson.dumps(response.model_dump()))
            except (asyncio.CancelledError, RuntimeError):
                pass
            except BaseException:
                self.log.error(f"Error in dummy agent: {traceback.format_exc()}")

        agent_dummy_task = asyncio.create_task(agent_dummy())

        await asyncio.sleep(0.1)

        connected_agents = await self.bbot_server.get_online_agents()
        assert len(connected_agents) == 2
        assert any(agent.id == self.agent_3.id for agent in connected_agents)

        agent_status = await self.bbot_server.get_agent_status(self.agent_3.id)
        assert agent_status == {"agent_status": "READY", "scan_status": "NOT_RUNNING"}

        # stop the agent dummy
        agent_dummy_task.cancel()
        with suppress(asyncio.CancelledError):
            await agent_dummy_task

        await asyncio.sleep(1)

        asset_activity_types = [a.type for a in self.asset_messages]
        assert asset_activity_types == ["AGENT_STATUS", "AGENT_STATUS", "AGENT_STATUS", "AGENT_STATUS", "AGENT_STATUS"]
        agent_statuses = [a.detail["status"] for a in self.asset_messages]
        assert agent_statuses == ["ONLINE", "READY", "ONLINE", "READY", "OFFLINE"]
