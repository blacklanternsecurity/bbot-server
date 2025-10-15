from tests.test_applets.base import BaseAppletTest


class TestAppletOpenPorts(BaseAppletTest):
    needs_watchdog = True

    async def setup(self):
        # at the beginning, everything should be empty
        assert await self.bbot_server.get_open_ports_by_host("www.evilcorp.com") == []
        assert await self.bbot_server.get_open_ports_by_host("www2.evilcorp.com") == []
        assert await self.bbot_server.get_open_ports_by_host("api.evilcorp.com") == []

        open_port_events = [a async for a in self.bbot_server.get_events(type="OPEN_TCP_PORT")]
        assert len(open_port_events) == 0

        assert [a.type for a in self.asset_messages] == []

    async def after_scan_1(self):
        # first scan should have five open ports
        assert set(await self.bbot_server.search_by_open_port(80)) == {
            "www.evilcorp.com",
            "www2.evilcorp.com",
            "t1.tech.evilcorp.com",
        }
        assert set(await self.bbot_server.search_by_open_port(443)) == {
            "t1.tech.evilcorp.com",
            "t2.tech.evilcorp.com",
        }

        assert await self.bbot_server.get_open_ports() == {
            "www.evilcorp.com": [80],
            "www2.evilcorp.com": [80],
            "t1.tech.evilcorp.com": [80, 443],
            "t2.tech.evilcorp.com": [443],
        }

        assert await self.bbot_server.get_open_ports_by_host("www.evilcorp.com") == [80]
        assert await self.bbot_server.get_open_ports_by_host("www2.evilcorp.com") == [80]
        assert await self.bbot_server.get_open_ports_by_host("api.evilcorp.com") == []
        assert await self.bbot_server.get_open_ports_by_host("t1.tech.evilcorp.com") == [80, 443]
        assert await self.bbot_server.get_open_ports_by_host("t2.tech.evilcorp.com") == [443]

        open_port_events = [a async for a in self.bbot_server.get_events(type="OPEN_TCP_PORT")]
        assert len(open_port_events) == 5

        port_asset_messages = [a for a in self.asset_messages if a.type.startswith("PORT_")]
        assert len(port_asset_messages) == 5
        assert [a.type for a in port_asset_messages] == [
            "PORT_OPENED",
            "PORT_OPENED",
            "PORT_OPENED",
            "PORT_OPENED",
            "PORT_OPENED",
        ]

        www = await self.bbot_server.get_asset("www.evilcorp.com")
        assert www.open_ports == [80]
        www2 = await self.bbot_server.get_asset("www2.evilcorp.com")
        assert www2.open_ports == [80]
        api = await self.bbot_server.get_asset("api.evilcorp.com")
        assert api.open_ports == []

    async def after_scan_2(self):
        # second scan should have a new open port on api.evilcorp.com
        assert set(await self.bbot_server.search_by_open_port(80)) == {
            "www.evilcorp.com",
            "www2.evilcorp.com",
            "t1.tech.evilcorp.com",
        }
        assert set(await self.bbot_server.search_by_open_port(443)) == {
            "t1.tech.evilcorp.com",
            "t2.tech.evilcorp.com",
            "api.evilcorp.com",
        }

        assert await self.bbot_server.get_open_ports_by_host("api.evilcorp.com") == [443]
        assert await self.bbot_server.get_open_ports_by_host("www.evilcorp.com") == [80]
        assert await self.bbot_server.get_open_ports_by_host("www2.evilcorp.com") == [80]

        open_port_events = [a async for a in self.bbot_server.get_events(type="OPEN_TCP_PORT")]
        assert len(open_port_events) == 8

        port_asset_messages = [a for a in self.asset_messages if a.type.startswith("PORT_")]
        assert len(port_asset_messages) == 6
        assert [a.type for a in port_asset_messages] == [
            "PORT_OPENED",
            "PORT_OPENED",
            "PORT_OPENED",
            "PORT_OPENED",
            "PORT_OPENED",
            "PORT_OPENED",
        ]

        www = await self.bbot_server.get_asset("www.evilcorp.com")
        assert www.open_ports == [80]
        www2 = await self.bbot_server.get_asset("www2.evilcorp.com")
        assert www2.open_ports == [80]
        api = await self.bbot_server.get_asset("api.evilcorp.com")
        assert api.open_ports == [443]

        # test stats
        stats = await self.bbot_server.get_stats()
        print(stats)
        assert sorted(stats["open_ports"].items()) == sorted({"80": 3, "443": 3}.items())

    async def after_archive(self):
        # after archiving, the first open port should be gone
        assert set(await self.bbot_server.search_by_open_port(80)) == {
            "www2.evilcorp.com",
        }
        assert set(await self.bbot_server.search_by_open_port(443)) == {
            "t2.tech.evilcorp.com",
            "api.evilcorp.com",
        }

        assert await self.bbot_server.get_open_ports() == {
            "www2.evilcorp.com": [80],
            "api.evilcorp.com": [443],
            "t2.tech.evilcorp.com": [443],
        }

        open_port_events = [a async for a in self.bbot_server.get_events(type="OPEN_TCP_PORT")]
        assert len(open_port_events) == 3

        port_asset_messages = [a for a in self.asset_messages if a.type.startswith("PORT_")]
        assert len(port_asset_messages) == 9
        assert [a.type for a in port_asset_messages] == [
            "PORT_OPENED",
            "PORT_OPENED",
            "PORT_OPENED",
            "PORT_OPENED",
            "PORT_OPENED",
            "PORT_OPENED",
            "PORT_CLOSED",
            "PORT_CLOSED",
            "PORT_CLOSED",
        ]

        www = await self.bbot_server.get_asset("www.evilcorp.com")
        assert www.open_ports == []
        www2 = await self.bbot_server.get_asset("www2.evilcorp.com")
        assert www2.open_ports == [80]
        api = await self.bbot_server.get_asset("api.evilcorp.com")
        assert api.open_ports == [443]
