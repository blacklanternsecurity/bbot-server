from tests.test_applets.base import BaseAppletTest


class TestAppletTechnologies(BaseAppletTest):
    needs_watchdog = True

    async def setup(self):
        # at the beginning, everything should be empty
        assert await self.bbot_server.get_technologies_for_host("tech1.evilcorp.com") == []
        assert await self.bbot_server.get_technologies_for_host("tech2.evilcorp.com") == []
        assert [t async for t in self.bbot_server.get_technologies()] == []

        technology_events = [a async for a in self.bbot_server.get_events(type="TECHNOLOGY")]
        assert len(technology_events) == 0

        assert [a.type for a in self.asset_messages] == []

    async def after_scan_1(self):
        # tech1 should have the same technology twice, once on port 80 and the other on 443
        tech1 = await self.bbot_server.get_technologies_for_host("tech1.evilcorp.com")
        assert len(tech1) == 2
        assert {(t.netloc, t.technology) for t in tech1} == {
            ("tech1.evilcorp.com:80", "cpe:/a:apache:http_server:2.4.12"),
            ("tech1.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
        }

        # tech2 should have only one technology
        tech2 = await self.bbot_server.get_technologies_for_host("tech2.evilcorp.com")
        assert len(tech2) == 1
        assert {(t.netloc, t.technology) for t in tech2} == {
            ("tech2.evilcorp.com:443", "cpe:/a:microsoft:internet_information_services"),
        }

        # all technologies should be listed
        all_techs = [t async for t in self.bbot_server.get_technologies()]
        assert len(all_techs) == 3
        assert {(t.netloc, t.technology) for t in all_techs} == {
            ("tech1.evilcorp.com:80", "cpe:/a:apache:http_server:2.4.12"),
            ("tech1.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
            ("tech2.evilcorp.com:443", "cpe:/a:microsoft:internet_information_services"),
        }

    async def after_scan_2(self):
        # nothing new has been discovered on tech1
        tech1 = await self.bbot_server.get_technologies_for_host("tech1.evilcorp.com")
        assert len(tech1) == 2
        assert {(t.netloc, t.technology) for t in tech1} == {
            ("tech1.evilcorp.com:80", "cpe:/a:apache:http_server:2.4.12"),
            ("tech1.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
        }

        # but we found apache on tech2
        tech2 = await self.bbot_server.get_technologies_for_host("tech2.evilcorp.com")
        assert len(tech2) == 2
        assert {(t.netloc, t.technology) for t in tech2} == {
            ("tech2.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
            ("tech2.evilcorp.com:443", "cpe:/a:microsoft:internet_information_services"),
        }

        # get technologies (brief)
        tech_brief = await self.bbot_server.get_technologies_brief(domain="evilcorp.com")
        assert tech_brief == {
            "cpe:/a:apache:http_server:2.4.12": 2,
            "cpe:/a:microsoft:internet_information_services": 1,
        }
        tech_brief = await self.bbot_server.get_technologies_brief(domain="tech2.evilcorp.com")
        assert tech_brief == {
            "cpe:/a:apache:http_server:2.4.12": 1,
            "cpe:/a:microsoft:internet_information_services": 1,
        }

        # search for apache
        techs = [t async for t in self.bbot_server.search_technology("apache")]
        assert len(techs) == 3
        assert set([(t.netloc, t.technology) for t in techs]) == {
            ("tech1.evilcorp.com:80", "cpe:/a:apache:http_server:2.4.12"),
            ("tech1.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
            ("tech2.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
        }

    async def after_archive(self):
        # after archiving, tech1 loses all its technologies
        tech1 = await self.bbot_server.get_technologies_for_host("tech1.evilcorp.com")
        assert len(tech1) == 0

        # tech2 has only apache
        tech2 = await self.bbot_server.get_technologies_for_host("tech2.evilcorp.com")
        assert len(tech2) == 1
        assert {(t.netloc, t.technology) for t in tech2} == {
            ("tech2.evilcorp.com:443", "cpe:/a:apache:http_server:2.4.12"),
        }
