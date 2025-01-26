from bbot_server_tests.test_applets.base import BaseAppletTest


class TestAppletOpenPorts(BaseAppletTest):
    async def setup(self):
        # at the beginning, everything should be empty
        assert await self.bbot_server.get_open_ports("www.evilcorp.com") == []
        assert await self.bbot_server.get_open_ports("mail2.evilcorp.com") == []

    async def after_scan_1(self):
        # first scan should have only one open port
        assert await self.bbot_server.get_open_ports("www.evilcorp.com") == [443]
        assert await self.bbot_server.get_open_ports("mail2.evilcorp.com") == []

    async def after_scan_2(self):
        # second scan should have two
        assert await self.bbot_server.get_open_ports("www.evilcorp.com") == [443]
        assert await self.bbot_server.get_open_ports("mail2.evilcorp.com") == [80]
