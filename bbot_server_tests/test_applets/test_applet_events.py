from ..conftest import *

from bbot_server_tests.test_applets.base import BaseAppletTest


class TestAppletEvents(BaseAppletTest):
    async def setup(self):
        route = self.bbot_server.route_maps["tail_events"]
        assert route.fastapi_route.path == "/events/tail"
        assert route.endpoint_type == "websocket"

    async def after_scan_1(self):
        # TODO: why does this change sometimes?
        assert 20 <= len(self.event_messages) <= 21

        # make sure our event store is populated
        # events = await self.bbot_server.get_events()
        # assert len(events) == len(self.event_messages)

    async def after_scan_2(self):
        assert 40 <= len(self.event_messages) <= 42

        # make sure the new events arrived in the event store
        # events = await self.bbot_server.get_events()
        # assert len(events) == len(self.event_messages)
