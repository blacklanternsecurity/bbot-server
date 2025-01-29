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

    async def after_scan_2(self):
        assert 40 <= len(self.event_messages) <= 42
