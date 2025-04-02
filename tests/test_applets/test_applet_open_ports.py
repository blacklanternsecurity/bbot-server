from tests.test_applets.base import BaseAppletTest


class TestAppletOpenPorts(BaseAppletTest):
    needs_watchdog = True

    async def setup(self):
        # at the beginning, everything should be empty
        assert await self.bbot_server.get_open_ports("openport80a.evilcorp.com") == []
        assert await self.bbot_server.get_open_ports("openport80b.evilcorp.com") == []
        assert await self.bbot_server.get_open_ports("openport443.evilcorp.com") == []

        open_port_events = [a async for a in self.bbot_server.get_events(type="OPEN_TCP_PORT")]
        assert len(open_port_events) == 0

        assert [a.type for a in self.asset_messages] == []

    async def after_scan_1(self):
        # first scan should have only one open port
        assert await self.bbot_server.get_open_ports("openport80a.evilcorp.com") == [80]
        assert await self.bbot_server.get_open_ports("openport80b.evilcorp.com") == [80]
        assert await self.bbot_server.get_open_ports("openport443.evilcorp.com") == []

        open_port_events = [a async for a in self.bbot_server.get_events(type="OPEN_TCP_PORT")]
        assert len(open_port_events) == 2

        assert len(self.asset_messages) == 2
        assert [a.type for a in self.asset_messages] == ["PORT_OPENED", "PORT_OPENED"]

    async def after_scan_2(self):
        # second scan should have two
        assert await self.bbot_server.get_open_ports("openport443.evilcorp.com") == [443]
        assert await self.bbot_server.get_open_ports("openport80a.evilcorp.com") == [80]
        assert await self.bbot_server.get_open_ports("openport80b.evilcorp.com") == [80]

        open_port_events = [a async for a in self.bbot_server.get_events(type="OPEN_TCP_PORT")]
        assert len(open_port_events) == 4

        assert len(self.asset_messages) == 3
        assert [a.type for a in self.asset_messages] == [
            "PORT_OPENED",
            "PORT_OPENED",
            "PORT_OPENED",
        ]

    async def after_archive(self):
        # after archiving, the first open port should be gone
        assert await self.bbot_server.get_open_ports("openport80a.evilcorp.com") == []
        assert await self.bbot_server.get_open_ports("openport80b.evilcorp.com") == [80]
        assert await self.bbot_server.get_open_ports("openport443.evilcorp.com") == [443]

        open_port_events = [a async for a in self.bbot_server.get_events(type="OPEN_TCP_PORT")]
        assert len(open_port_events) == 2

        assert len(self.asset_messages) == 4
        assert [a.type for a in self.asset_messages] == [
            "PORT_OPENED",
            "PORT_OPENED",
            "PORT_OPENED",
            "PORT_CLOSED",
        ]
