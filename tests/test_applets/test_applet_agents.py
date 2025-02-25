import json
import asyncio
import websockets

from tests.test_applets.base import BaseAppletTest


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

        agent_2 = await self.bbot_server.get_agent(id=new_agent_2.id)
        assert agent_2 is not None
        assert agent_2.name == new_agent_2.name
        assert agent_2.description == new_agent_2.description
        assert agent_2.id == new_agent_2.id

        agent_3 = await self.bbot_server.get_agent(name=new_agent_3.name)
        assert agent_3 is not None
        assert agent_3.name == new_agent_3.name
        assert agent_3.description == new_agent_3.description
        assert agent_3.id == new_agent_3.id

        self.agent_3 = agent_3

    async def after_scan_1(self):
        # we only run this test if we're using the HTTP interface
        if self.bbot_server.interface_type != "http":
            return

        # connect to the agent, send a message, and disconnect
        agent_url = f"ws://localhost:8807/v1/scans/agents/dock/{self.agent_3.id}"

        connected_agents = await self.bbot_server.get_online_agents()
        assert len(connected_agents) == 1

        async with websockets.connect(agent_url) as websocket:
            # Send a message to the agent
            message = {"type": "greeting", "content": "Hello, Agent!"}
            await websocket.send(json.dumps(message))

            # Optionally, receive a response
            response = await websocket.recv()
            print(f"Received response: {response}")

            connected_agents = await self.bbot_server.get_online_agents()
            assert len(connected_agents) == 2
            assert any(agent.id == self.agent_3.id for agent in connected_agents)

        await asyncio.sleep(1)

        asset_activity_types = [a.type for a in self.asset_messages]
        assert asset_activity_types.count("AGENT_CONNECTED") == 2
        assert asset_activity_types.count("AGENT_DISCONNECTED") == 1
