from contextlib import suppress

from ..conftest import *

from bbot_server_tests.test_applets.base import BaseAppletTest


class TestAppletEvents(BaseAppletTest):
    async def setup(self):
        route = self.bbot_server.route_maps["tail_events"]
        assert route.fastapi_route.path == "/events/tail"
        assert route.endpoint_type == "websocket"

    async def after_scan_1(self):
        assert len(self.event_messages) == 20

    async def after_scan_2(self):
        assert len(self.event_messages) == 41
